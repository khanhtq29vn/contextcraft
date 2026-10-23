from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pathspec
import pytest

from contextcraft.languages.base import LanguageSpec
from contextcraft.languages.builtin import TextLanguage, default_registry
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.registry import LanguageRegistry
from contextcraft.models import CompilationConfig, RepositoryNotFoundError
from contextcraft.scanner import RepositoryScanner


def test_scanner_uses_custom_registry_extensions_filenames_and_ignores(tmp_path: Path) -> None:
    class CustomLanguage(TextLanguage):
        spec = LanguageSpec(
            id="custom",
            extensions=frozenset({".custom"}),
            filenames=frozenset({"Customfile"}),
            ignore_patterns=("generated/", "*.cache"),
        )

    registry = LanguageRegistry()
    registry.register(CustomLanguage)
    for name in (
        "main.CUSTOM",
        "Customfile",
        "notes.txt",
        "ignored.cache",
        "generated/skip.custom",
        "nested/generated/skip.custom",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source")
    outcome = RepositoryScanner(registry).scan(tmp_path)
    by_path = {file.rel_path: file for file in outcome.files}

    assert set(by_path) == {"main.CUSTOM", "Customfile", "notes.txt"}
    assert by_path["main.CUSTOM"].candidates == (CustomLanguage,)
    assert by_path["Customfile"].candidates == (CustomLanguage,)
    assert by_path["notes.txt"].candidates == ()
    assert outcome.ignored_files_skipped == 3


def test_scanner_reads_registry_changes_on_each_scan(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("library")
    registry = LanguageRegistry()
    scanner = RepositoryScanner(registry)
    assert len(scanner.scan(tmp_path).files) == 1

    registry.register(JavaScriptLanguage)

    assert scanner.scan(tmp_path).files == []


def test_scanner_scopes_nested_ignore_rules_and_negations(tmp_path: Path) -> None:
    paths = {
        ".gitignore": "*.log\nroot-only.txt\n",
        "root-only.txt": "ignored",
        "root.log": "ignored",
        "src/.gitignore": "secret.txt\n/anchored.txt\n!keep.log\n",
        "src/secret.txt": "ignored",
        "src/deep/secret.txt": "ignored recursively",
        "src/anchored.txt": "ignored",
        "src/deep/anchored.txt": "kept",
        "src/keep.log": "kept",
        "src/deep/debug.log": "ignored by root",
        "other/secret.txt": "kept",
        "other/keep.log": "ignored",
    }
    for name, content in paths.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    outcome = RepositoryScanner(LanguageRegistry()).scan(tmp_path)

    assert {file.rel_path for file in outcome.files} == {
        "src/deep/anchored.txt",
        "src/keep.log",
        "other/secret.txt",
    }


def test_scanner_respects_all_control_files_and_git_exclude(tmp_path: Path) -> None:
    for name in (".gitignore", ".ignore", ".contextignore", ".repomixignore"):
        (tmp_path / name).write_text(name + ".data\n")
        (tmp_path / (name + ".data")).write_text("ignored")
    (tmp_path / ".git" / "info").mkdir(parents=True)
    (tmp_path / ".git" / "info" / "exclude").write_text("excluded.data\n")
    (tmp_path / "excluded.data").write_text("ignored")
    (tmp_path / "keep.js").write_text("const value = 1;")

    scanner = RepositoryScanner(default_registry())
    assert [file.rel_path for file in scanner.scan(tmp_path).files] == ["keep.js"]
    no_ignores = RepositoryScanner(default_registry(), CompilationConfig(respect_gitignore=False))
    assert len(no_ignores.scan(tmp_path).files) == 6


def test_scanner_skips_binary_oversized_empty_and_symlinked_files(tmp_path: Path) -> None:
    (tmp_path / "good.js").write_text("const x = 1;")
    (tmp_path / "bad.dat").write_bytes(b"binary\x00content")
    (tmp_path / "invalid.dat").write_bytes(b"\xff\xfeinvalid")
    (tmp_path / "large.js").write_bytes(b"x" * 65)
    (tmp_path / "empty.js").write_bytes(b"")
    (tmp_path / "link.js").symlink_to(tmp_path / "good.js")
    (tmp_path / "linked-dir").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / ".gitignore").symlink_to(tmp_path / "good.js")

    outcome = RepositoryScanner(default_registry(), CompilationConfig(max_file_size_bytes=64)).scan(
        tmp_path
    )

    assert [file.rel_path for file in outcome.files] == ["good.js"]
    assert outcome.binary_files_skipped == 2
    assert outcome.ignored_files_skipped == 5


def test_scanner_filters_includes_excludes_and_preserves_bytes(tmp_path: Path) -> None:
    source = 'const café = "你好";\r\n'.encode()
    for name in (
        "src/main.js",
        "src/skip.js",
        "src/nested/main.js",
        "src/nested/skip.js",
        "main.js",
        "notes.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source)
    config = CompilationConfig(include_patterns=["src/**/*.js"], exclude_patterns=["**/skip.js"])

    outcome = RepositoryScanner(default_registry(), config).scan(tmp_path)

    assert [file.rel_path for file in outcome.files] == ["src/main.js", "src/nested/main.js"]
    for file in outcome.files:
        assert file.source == source
        assert file.size_bytes == len(source)
        assert file.candidates == (JavaScriptLanguage,)


def test_scanner_does_not_load_ignores_from_pruned_directories(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n*.log\n")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / ".gitignore").write_text("!../keep.log\n")
    (tmp_path / "keep.log").write_text("ignored")

    assert RepositoryScanner(default_registry()).scan(tmp_path).files == []


def test_scanner_rejects_missing_or_file_roots(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("source")
    scanner = RepositoryScanner(default_registry())
    for path in (tmp_path / "missing", tmp_path / "file"):
        with pytest.raises(RepositoryNotFoundError):
            scanner.scan(path)


def test_scanner_reuses_identical_rules_and_reloads_them_on_next_scan(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.log\n")
    for index in range(20):
        directory = tmp_path / str(index)
        directory.mkdir()
        (directory / "keep.txt").write_text("source")
        (directory / "skip.log").write_text("ignored")
    scanner = RepositoryScanner(LanguageRegistry())
    with patch.object(
        pathspec.PathSpec, "from_lines", wraps=pathspec.PathSpec.from_lines
    ) as compile_spec:
        first = scanner.scan(tmp_path)

    assert len(first.files) == 20
    assert compile_spec.call_count == 2  # Include filter and one shared ignore spec.
    (tmp_path / ".gitignore").write_text("*.txt\n")
    second = scanner.scan(tmp_path)
    assert len(second.files) == 20
    assert all(file.rel_path.endswith("skip.log") for file in second.files)
