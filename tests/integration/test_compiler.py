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
from contextcraft.languages.base import LanguageSpec
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.registry import LanguageRegistry


def test_sdk_end_to_end_markdown_xml_and_json(sample_repo: Path) -> None:
    """Verify `ContextCraft.compile()` produces valid Markdown, XML, and JSON with secrets scrubbed."""
    cc = ContextCraft(budget_tokens="2k", focus_query="JWT authentication")

    # 1. Markdown output
    md_res = cc.compile(sample_repo, output_format=OutputFormat.MARKDOWN)
    assert "# Repository Context:" in md_res.markdown
    assert "## Repository Directory Tree" in md_res.text_content
    assert "sk-proj-1234567890" not in md_res.content
    assert md_res.stats.secrets_redacted >= 1
    assert md_res.stats.compressed_tokens <= 2000

    # 2. XML output (must parse cleanly as well-formed XML)
    xml_res = cc.compile(sample_repo, output_format="xml")
    assert xml_res.stats.compressed_tokens <= 2000
    assert "sk-proj-1234567890" not in xml_res.content
    root_elem = ET.fromstring(xml_res.content)
    assert root_elem.tag == "repository_context"

    # 3. JSON output (must deserialize cleanly as valid JSON)
    json_res = cc.compile(sample_repo, output_format=OutputFormat.JSON)
    assert json_res.stats.compressed_tokens <= 2000
    payload = json.loads(json_res.content)
    assert payload["budget_tokens"] == 2000
    assert isinstance(payload["files"], list)


@pytest.mark.parametrize("fmt", ["markdown", "xml", "json"])
@pytest.mark.parametrize("budget", [30, 180, 450, 800, 2000, 5000])
def test_compiler_respects_real_emitted_token_budgets(
    sample_repo: Path, fmt: str, budget: int
) -> None:
    result = ContextCraft(budget_tokens=budget, output_format=fmt).compile(sample_repo)

    assert result.stats.compressed_tokens <= budget
    assert result.stats.compressed_tokens == TokenCounter().count(result.content)
    assert result.stats.secrets_redacted >= 1
    assert "sk-proj-1234567890" not in result.content
    assert sum(result.stats.fidelity_counts.values()) == len(result.files)
    if fmt == "xml":
        assert ET.fromstring(result.content).tag == "repository_context"
    elif fmt == "json":
        json.loads(result.content)
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
    config = CompilationConfig(budget_tokens=5000, focus_files=["README.md"])
    compiler = ContextCraft(config)
    config.focus_files.append("mutated")

    first = compiler.compile(
        sample_repo, budget_tokens=450, output_format="json", focus_files=["models.py"]
    )
    second = compiler.compile(sample_repo)

    assert first.stats.budget_tokens == 450
    assert second.stats.budget_tokens == 5000
    assert second.output_format == "markdown"
    assert compiler.config.focus_files == ["README.md"]


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


@pytest.mark.parametrize("budget", [180, 450, 800, 1400, 5000])
def test_knapsack_optimizer_strictly_respects_all_token_budgets(
    sample_repo: Path,
    budget: int,
) -> None:
    """Verify compiled output never exceeds `budget_tokens` across tight and generous budgets."""
    cc = ContextCraft(budget_tokens=budget, focus_query="JWT verify_token")
    result = cc.compile(sample_repo)

    assert result.stats.compressed_tokens <= budget
    assert result.stats.budget_tokens == budget
