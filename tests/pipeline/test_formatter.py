from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contextcraft import CompilationConfig, ContextCraft, FidelityLevel
from contextcraft.ast import ParsedAst
from contextcraft.elider import Elider, TokenCounter
from contextcraft.formatter import ArtifactFormatter
from contextcraft.languages.builtin import PythonLanguage
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.models import FileAnalysis


def test_xml_handles_cdata_end_markers_and_xml_forbidden_characters(tmp_path: Path) -> None:
    # Keep Windows-invalid filename characters in metadata, not on disk.
    name = 'a&"]]>.js'
    source = b'const value = "]]> & \x01";'
    counter = TokenCounter()
    parsed = ParsedAst(source=source)
    file = FileAnalysis(
        rel_path=name,
        abs_path=str(tmp_path / "source.js"),
        language="javascript",
        size_bytes=len(source),
        parsed=parsed,
        tiers=Elider(counter).render(parsed, JavaScriptLanguage),
        selected_fidelity=FidelityLevel.FULL,
    )
    formatter = ArtifactFormatter(CompilationConfig(output_format="xml"), counter)
    result = formatter.format_result(
        root_path=tmp_path,
        files=[file],
        total_files_discovered=1,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )
    root = ET.fromstring(result.content)
    element = root.find("./files/file")

    assert element is not None
    assert element.attrib["path"] == name
    assert element.text == 'const value = "]]> & \\u0001";'


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_markdown_fences_cannot_be_closed_by_file_contents(tmp_path: Path, newline: str) -> None:
    source = f"``````{newline}source{newline}``````{newline}"
    (tmp_path / "example.unknown").write_bytes(source.encode("utf-8"))

    result = ContextCraft().compile(tmp_path)

    assert f"```````text\n{source}```````" in result.content


def test_minimal_json_is_valid_with_a_character_counter() -> None:
    class Counter:
        def count(self, text: str) -> int:
            return len(text)

    formatter = ArtifactFormatter(
        CompilationConfig(budget_tokens=1, output_format="json"), Counter()
    )
    result = formatter.format_result(
        root_path=".",
        files=[],
        total_files_discovered=0,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )

    assert result.stats.compressed_tokens == 1
    assert json.loads(result.content) == 0


def test_budgeted_tree_preserves_small_trees(sample_repo: Path) -> None:
    files = ContextCraft().analyze_repository(sample_repo)
    formatter = ArtifactFormatter(CompilationConfig(budget_tokens=32000))

    assert formatter.render_budgeted_directory_tree(files, "repo") == (
        formatter.render_directory_tree(files, "repo")
    )


def test_budgeted_tree_uses_injected_counter_and_handles_tiny_budgets() -> None:
    class Counter:
        def count(self, text: str) -> int:
            return len(text)

    formatter = ArtifactFormatter(CompilationConfig(budget_tokens=10), Counter())

    assert formatter.render_budgeted_directory_tree([], "very-long-root-name") == ""


def test_overflow_trimming_sacrifices_bodies_before_api_breadth(tmp_path: Path) -> None:
    class Counter:
        def count(self, text: str) -> int:
            return len(text)

    (tmp_path / "critical.py").write_text('def critical():\n    return "' + "x" * 5000 + '"\n')
    (tmp_path / "api.py").write_text(
        "def first():\n    return 1\ndef second():\n    return 2\ndef third():\n    return 3\n"
    )
    files = ContextCraft().analyze_repository(tmp_path)
    counter = Counter()
    for file in files:
        file.tiers = Elider(counter).render(file.parsed, PythonLanguage)
        file.selected_fidelity = FidelityLevel.FULL
        file.pagerank_score = 0.9 if file.rel_path == "critical.py" else 0.1
    formatter = ArtifactFormatter(CompilationConfig(budget_tokens=1200), counter)

    result = formatter.format_result(
        root_path=tmp_path,
        files=files,
        total_files_discovered=2,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )

    assert counter.count(result.content) <= 1200
    assert all(file.selected_fidelity > FidelityLevel.TREE for file in files)
    assert result.stats.preserved_signatures_pct == 100


def test_compact_tree_cache_ignores_fidelity_but_tracks_tree_inputs(sample_repo: Path) -> None:
    from unittest.mock import Mock

    files = ContextCraft().analyze_repository(sample_repo)
    counter = Mock()
    counter.count.side_effect = len
    config = CompilationConfig(budget_tokens=1000)
    formatter = ArtifactFormatter(config, counter)
    first = formatter.render_budgeted_directory_tree(files, "repo")
    calls = counter.count.call_count
    assert "files omitted" in first
    for file in files:
        file.selected_fidelity = FidelityLevel.FULL

    assert formatter.render_budgeted_directory_tree(files, "repo") == first
    assert counter.count.call_count == calls + 1

    for change in ("rank", "path", "root", "budget", "files"):
        root = "repo"
        if change == "rank":
            files[-1].pagerank_score = 100
        elif change == "path":
            files[0].rel_path = "renamed.py"
        elif change == "root":
            root = "different"
        elif change == "budget":
            config.budget_tokens = 3000
        else:
            files = files[:-1]
        expected = ArtifactFormatter(config, counter).render_budgeted_directory_tree(files, root)
        assert formatter.render_budgeted_directory_tree(files, root) == expected


def test_full_tree_refreshes_fidelity_badges(sample_repo: Path) -> None:
    files = ContextCraft().analyze_repository(sample_repo)
    formatter = ArtifactFormatter(CompilationConfig(budget_tokens=32000))
    before = formatter.render_budgeted_directory_tree(files, "repo")
    files[0].selected_fidelity = FidelityLevel.FULL
    after = formatter.render_budgeted_directory_tree(files, "repo")

    assert after != before
    assert after == formatter.render_directory_tree(files, "repo")
