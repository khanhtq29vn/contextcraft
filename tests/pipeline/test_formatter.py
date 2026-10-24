from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contextcraft import CompilationConfig, ContextCraft, FidelityLevel
from contextcraft.ast import ParsedAst
from contextcraft.ast.parser import parse
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


def test_overflow_trimming_keeps_pinned_files_until_others_are_gone(tmp_path: Path) -> None:
    counter = TokenCounter()
    files = []
    for name, rank in (("pinned.py", 0.1), ("central.py", 0.9)):
        source = "".join(
            f"def {name[:-3]}_{index}(value):\n    return value + {index}\n" for index in range(40)
        ).encode()
        parsed = parse(source, PythonLanguage)
        files.append(
            FileAnalysis(
                rel_path=name,
                abs_path=str(tmp_path / name),
                language="python",
                size_bytes=len(source),
                parsed=parsed,
                tiers=Elider(counter).render(parsed, PythonLanguage),
                pagerank_score=rank,
                selected_fidelity=FidelityLevel.FULL,
            )
        )
    budget = files[0].raw_tokens + files[1].tiers[FidelityLevel.SIGNATURES].tokens + 250
    config = CompilationConfig(budget_tokens=budget, pinned_full_files=["pinned.py"])

    result = ArtifactFormatter(config, counter).format_result(
        root_path=tmp_path,
        files=files,
        total_files_discovered=2,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )
    fidelity = {file.rel_path: file.selected_fidelity for file in result.files}

    assert result.stats.compressed_tokens <= budget
    assert fidelity["pinned.py"] == FidelityLevel.FULL
    assert fidelity["central.py"] < FidelityLevel.FULL


def test_formatter_trims_pinned_files_when_nothing_else_is_left(tmp_path: Path) -> None:
    counter = TokenCounter()
    source = "".join(
        f"def legacy_{index}(value):\n    return value * {index}\n" for index in range(80)
    )
    parsed = parse(source.encode(), PythonLanguage)
    pinned = FileAnalysis(
        rel_path="legacy.py",
        abs_path=str(tmp_path / "legacy.py"),
        language="python",
        size_bytes=len(source),
        parsed=parsed,
        tiers=Elider(counter).render(parsed, PythonLanguage),
        pagerank_score=1.0,
        selected_fidelity=FidelityLevel.FULL,
    )
    budget = pinned.raw_tokens // 2
    config = CompilationConfig(budget_tokens=budget, pinned_full_files=["legacy.py"])

    result = ArtifactFormatter(config, counter).format_result(
        root_path=tmp_path,
        files=[pinned],
        total_files_discovered=1,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )

    assert result.stats.compressed_tokens <= budget
    assert pinned.selected_fidelity < FidelityLevel.FULL


def test_pinned_file_that_overflows_its_estimate_leaves_room_for_other_files(
    tmp_path: Path,
) -> None:
    # Quotes and backslashes make the pinned file cost far more in JSON than estimated.
    (tmp_path / "legacy.py").write_text(
        "".join(
            f'def legacy_{index}(value):\n    """Doc \\"{index}\\" with \'quotes\' and \\\\ slashes."""\n'
            f'    return {{"k{index}": "v\\t{index}", "p": r"C:\\\\x\\\\{index}"}}\n'
            for index in range(60)
        )
    )
    for index in range(12):
        (tmp_path / f"mod_{index}.py").write_text(
            "".join(
                f"def run_{index}_{step}(value):\n    return value + {step}\n" for step in range(6)
            )
        )

    # Only JSON escaping makes the pinned file overflow its estimate here.
    result = ContextCraft(output_format="json").compile(
        tmp_path, budget_tokens=3400, pinned_full_files=["legacy.py"]
    )
    fidelity = {file.rel_path: file.selected_fidelity for file in result.files}

    assert result.stats.compressed_tokens <= 3400
    assert fidelity["legacy.py"] >= FidelityLevel.SKELETON
    assert any(
        level > FidelityLevel.TREE for path, level in fidelity.items() if path != "legacy.py"
    )
    assert result.stats.budget_utilization_pct >= 90


def test_large_overflows_are_trimmed_in_a_few_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(150):
        (tmp_path / f"strings_{index:03}.py").write_text(
            "".join(f'S{step} = "\\"q\\" \\\\ \\t {index}-{step}"\n' for step in range(8))
        )
    renders = 0
    render = ArtifactFormatter._render

    def counting_render(
        self: ArtifactFormatter, name: str, files: list[FileAnalysis], tree: str
    ) -> str:
        nonlocal renders
        renders += 1
        return render(self, name, files, tree)

    monkeypatch.setattr(ArtifactFormatter, "_render", counting_render)
    snapshot = ContextCraft(output_format="json").analyze(tmp_path)
    budget = int(sum(file.raw_tokens for file in snapshot.files) * 1.2)

    result = snapshot.render(budget_tokens=budget)

    # JSON escaping overflows the estimate by thousands of tokens; trimming one file per
    # render took about 60 renders.
    assert result.stats.compressed_tokens <= budget
    assert result.stats.budget_utilization_pct >= 95
    assert renders <= 15


def test_trimmed_pins_keep_their_priority_after_re_allocation(tmp_path: Path) -> None:
    def escaped(tag: str, count: int) -> str:
        return "".join(
            f'def {tag}_{index}(value):\n    """Doc \\"{index}\\" with \'quotes\' and \\\\ slashes."""\n'
            f'    return {{"k{index}": "v\\t{index}", "p": r"C:\\\\x\\\\{index}"}}\n'
            for index in range(count)
        )

    (tmp_path / "legacy.py").write_text(escaped("legacy", 60))
    (tmp_path / "legacy2.py").write_text(escaped("old", 40))
    (tmp_path / "core.py").write_text(
        "from legacy import *\nfrom legacy2 import *\n"
        + "".join(
            f"class Thing{index}:\n    def go(self, x):\n        return x * {index}\n"
            for index in range(30)
        )
    )
    for index in range(12):
        (tmp_path / f"user_{index}.py").write_text(
            f"import core\nimport legacy\n\ndef use_{index}():\n    return core.Thing{index}().go({index})\n"
        )
    pins = ["core.py", "legacy.py", "legacy2.py"]
    snapshot = ContextCraft(output_format="json").analyze(tmp_path)

    for budget in range(2000, 6001, 400):
        result = snapshot.render(budget_tokens=budget, pinned_full_files=pins)
        fidelity = {file.rel_path: file.selected_fidelity for file in result.files}

        assert result.stats.compressed_tokens <= budget
        # core.py has the highest PageRank of the pins and its full source fits.
        assert fidelity["core.py"] == FidelityLevel.FULL
        assert fidelity["legacy.py"] >= FidelityLevel.SIGNATURES
        assert fidelity["legacy2.py"] >= FidelityLevel.SIGNATURES


@pytest.mark.parametrize(("output_format", "low", "high"), [("markdown", 10, 24), ("json", 40, 80)])
def test_file_wrapper_cost_excludes_one_time_section_headers(
    output_format: str, low: int, high: int
) -> None:
    formatter = ArtifactFormatter(CompilationConfig(output_format=output_format))

    assert low <= formatter._file_wrapper_tokens("repo", "repo/\n") <= high


def test_many_tiny_pins_still_fill_a_json_budget(tmp_path: Path) -> None:
    for index in range(200):
        (tmp_path / f"strings_{index:03}.py").write_text(
            "".join(f'S{step} = "\\"q\\" \\\\ \\t {index}-{step}"\n' for step in range(8))
        )
    snapshot = ContextCraft(output_format="json").analyze(tmp_path)
    budget = sum(file.raw_tokens for file in snapshot.files) // 2

    result = snapshot.render(budget_tokens=budget, pinned_full_files=["*.py"])

    # The per-file JSON wrapper dwarfs these files, so the first allocation overflows
    # badly; re-allocation and measured pin raising must still use the budget.
    assert result.stats.compressed_tokens <= budget
    assert result.stats.budget_utilization_pct >= 99
