from __future__ import annotations

from pathlib import Path

import pytest

from contextcraft import ContextCraft
from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry
from contextcraft.models import FileAnalysis
from contextcraft.retention import code_symbols, retained_symbols


@pytest.mark.parametrize(
    "language_id,source",
    [
        ("python", "class A:\n def run(self): return 1\nclass B:\n def run(self): return 2\n"),
        ("javascript", "class A { run() { return 1; } } class B { run() { return 2; } }"),
        (
            "java",
            "package demo; class A { public int run() { return 1; } } class B { public int run() { return 2; } }",
        ),
        (
            "csharp",
            "namespace Demo { public class A { public int run() { return 1; } } public class B { public int run() { return 2; } } }",
        ),
        (
            "rust",
            "pub struct A {} impl A { pub fn run(&self) {} } pub struct B {} impl B { pub fn run(&self) {} }",
        ),
    ],
)
def test_retention_matches_enclosing_types(language_id: str, source: str) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source.encode(), language)
    assert not parsed.has_errors
    file = FileAnalysis("api", "api", language_id, len(parsed.source), parsed)
    method = next(symbol for symbol in parsed.symbols if symbol.qualified_name == "A.run")

    content = language.build_selected(parsed, [method])
    retained = retained_symbols(file, content, language=language)

    assert not parse(content.encode(), language).has_errors
    assert {symbol.qualified_name for symbol in retained} == {"A", "A.run"}
    assert len(code_symbols(parsed)) == 4
    assert parsed.source == source.encode()
    assert len(parsed.symbols) == 4
    if language_id == "java":
        assert "package demo;" in content
    elif language_id == "csharp":
        assert "namespace Demo" in content
    elif language_id == "rust":
        assert "impl A" in content


def test_retention_does_not_count_signatures_in_strings(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text("def run(): return 1\n")
    file = ContextCraft().analyze_repository(tmp_path)[0]

    assert retained_symbols(file, 'value = "def run():"\n') == []


def test_retention_counts_duplicate_declarations_only_once_per_occurrence(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text("def run(): return 1\ndef run(): return 2\n")
    file = ContextCraft().analyze_repository(tmp_path)[0]

    assert len(retained_symbols(file, "def run(): ...\n")) == 1


def test_code_symbols_exclude_private_local_and_non_code_symbols(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Project\n## Usage\n")
    (tmp_path / "config.json").write_text('{"key": "value"}')
    (tmp_path / "api.py").write_text(
        "def run():\n    def helper(): return 1\n    return helper()\ndef _private(): return 2\n"
    )
    files = ContextCraft().analyze_repository(tmp_path)

    assert [symbol.qualified_name for file in files for symbol in code_symbols(file.parsed)] == [
        "run"
    ]
    assert [
        symbol.qualified_name
        for file in files
        for symbol in code_symbols(file.parsed, public_only=False)
    ] == ["run", "_private"]
