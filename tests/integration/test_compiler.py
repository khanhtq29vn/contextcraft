from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

from contextcraft import (
    CompilationConfig,
    ContextCraft,
    FidelityLevel,
    InvalidBudgetError,
    OutputFormat,
    TokenCounter,
)
from contextcraft.formatter import ArtifactFormatter
from contextcraft.languages.base import LanguageSpec
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.registry import LanguageRegistry


@pytest.mark.parametrize("fmt", ["markdown", "xml", "json"])
@pytest.mark.parametrize(
    "budget,focus_query",
    [(30, None), (180, None), (450, None), (2000, "JWT authentication"), (5000, None)],
)
def test_compiler_respects_real_emitted_token_budgets(
    sample_repo: Path, fmt: str, budget: int, focus_query: str | None
) -> None:
    result = ContextCraft(budget_tokens=budget, output_format=fmt, focus_query=focus_query).compile(
        sample_repo
    )

    assert result.markdown == result.text_content == result.content
    assert result.stats.budget_tokens == budget
    assert result.stats.compressed_tokens == TokenCounter().count(result.content) <= budget
    assert result.stats.secrets_redacted >= 1
    assert "sk-proj-1234567890" not in result.content
    assert sum(result.stats.fidelity_counts.values()) == len(result.files)
    if fmt == "xml":
        assert ET.fromstring(result.content).tag == "repository_context"
    elif fmt == "json":
        payload = json.loads(result.content)
        if budget >= 2000:
            assert payload["budget_tokens"] == budget
            assert payload["focus_query"] == focus_query
            assert isinstance(payload["files"], list)
    elif budget >= 2000:
        assert "# Repository Context:" in result.content
        assert "## Repository Directory Tree" in result.content
    for file in result.files:
        assert "sk-proj-1234567890" not in file.parsed.source.decode()


def test_compiler_tiny_budget_behavior(sample_repo: Path) -> None:
    for fmt in ("markdown", "json"):
        result = ContextCraft(budget_tokens=1, output_format=fmt).compile(sample_repo)
        assert result.stats.compressed_tokens <= 1
        if fmt == "json":
            json.loads(result.content)
    with pytest.raises(InvalidBudgetError, match="XML"):
        ContextCraft(budget_tokens=1, output_format="xml").compile(sample_repo)


def test_compiler_remains_budget_safe_with_offline_token_counting(sample_repo: Path) -> None:
    with patch("contextcraft.elider.tiktoken.get_encoding", side_effect=OSError("offline")):
        result = ContextCraft(budget_tokens=450).compile(sample_repo)
        counter = TokenCounter()

    assert counter.count(result.content) == result.stats.compressed_tokens <= 450


def test_compiler_unknown_files_preserve_source_and_use_text_fallback(tmp_path: Path) -> None:
    source = "unrecognized source format\r\n"
    (tmp_path / "file.unknown").write_bytes(source.encode())
    registry = LanguageRegistry()

    result = ContextCraft(registry=registry).compile(tmp_path)

    assert len(result.files) == 1
    assert result.files[0].language == "text"
    assert result.files[0].parsed.source == source.encode()
    assert result.files[0].selected_content == source


def test_compiler_uses_injected_registry_and_selects_valid_candidates(tmp_path: Path) -> None:
    class WrongLanguage(JavaScriptLanguage):
        spec = LanguageSpec(id="wrong", parser_id="javascript", extensions=frozenset({".shared"}))

    from contextcraft.languages.builtin import PythonLanguage

    class RightLanguage(PythonLanguage):
        spec = LanguageSpec(
            id="right",
            parser_id="python",
            extensions=frozenset({".shared"}),
            ignore_patterns=("skip/",),
        )

    registry = LanguageRegistry()
    registry.register(WrongLanguage)
    registry.register(RightLanguage)
    (tmp_path / "run.shared").write_text("def run(value):\n    return transform(value)\n")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "ignored.shared").write_text("ignored")

    result = ContextCraft(registry=registry).compile(tmp_path)

    assert [file.language for file in result.files] == ["right"]
    assert [symbol.name for symbol in result.files[0].symbols] == ["run"]


def test_compiler_configuration_overrides_are_isolated(sample_repo: Path) -> None:
    config = CompilationConfig(
        budget_tokens=5000, focus_query="authentication", focus_files=["README.md"]
    )
    compiler = ContextCraft(config)
    config.focus_files.append("mutated")

    first = compiler.compile(
        sample_repo,
        budget_tokens=450,
        output_format=OutputFormat.JSON,
        focus_query="JWT verify_token",
        focus_files=["models.py"],
    )
    second = compiler.compile(sample_repo)

    assert first.stats.budget_tokens == 450
    assert second.stats.budget_tokens == 5000
    assert second.output_format == "markdown"
    assert compiler.config.focus_files == ["README.md"]
    assert compiler.config.focus_query == "authentication"


def test_compiler_redaction_can_be_explicitly_disabled(tmp_path: Path) -> None:
    secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    (tmp_path / "keys.js").write_text(f'const token = "{secret}";')
    compiler = ContextCraft()

    safe = compiler.compile(tmp_path)
    unsafe = compiler.compile(tmp_path, redact_secrets=False)

    assert secret not in safe.content
    assert safe.stats.secrets_redacted == 1
    assert secret in unsafe.content
    assert unsafe.stats.secrets_redacted == 0
    assert compiler.config.redact_secrets


def test_empty_repository_and_single_file(tmp_path: Path) -> None:
    empty = ContextCraft().compile(tmp_path)
    assert empty.stats.files_compiled == 0
    assert empty.files == []
    (tmp_path / "single.js").write_text("export function run() { return 1; }")

    result = ContextCraft().compile(tmp_path)

    assert result.files[0].pagerank_score == 1.0
    assert result.files[0].selected_fidelity == FidelityLevel.FULL


@pytest.mark.parametrize("fmt", ["markdown", "xml", "json"])
def test_large_directory_tree_leaves_budget_for_code(tmp_path: Path, fmt: str) -> None:
    for index in range(80):
        path = tmp_path / f"module_{index:03d}_with_a_long_descriptive_filename.py"
        path.write_text(f"def action_{index}():\n    return {index}\n", encoding="utf-8")
    compiler = ContextCraft(budget_tokens=1000, output_format=fmt)
    analyses = compiler.analyze_repository(tmp_path)

    counter = TokenCounter()
    full_tree = ArtifactFormatter.render_directory_tree(analyses, tmp_path.name)
    assert counter.count(full_tree) > 1000

    result = compiler.compile(tmp_path)

    assert result.stats.compressed_tokens == counter.count(result.content) <= 1000
    assert result.stats.tree_overhead_tokens <= 100
    assert result.stats.preserved_signatures_pct > 0
    assert any(file.selected_fidelity > FidelityLevel.TREE for file in result.files)
    assert "files omitted" in result.content
    if fmt == "xml":
        ET.fromstring(result.content)
    elif fmt == "json":
        json.loads(result.content)


def test_oversized_file_is_tree_only_when_no_complete_tier_fits(tmp_path: Path) -> None:
    source = "".join(
        f"def operation_{index}(value: int) -> int:\n    return value + {index}\n"
        for index in range(50)
    )
    (tmp_path / "api.py").write_text(source, encoding="utf-8")

    result = ContextCraft(budget_tokens=350).compile(tmp_path)
    file = result.files[0]

    assert result.stats.compressed_tokens <= 350
    assert file.selected_fidelity == FidelityLevel.TREE
    assert all(file.tiers[level].tokens > 350 for level in FidelityLevel if level)
    assert file.parsed.source == source.encode()
