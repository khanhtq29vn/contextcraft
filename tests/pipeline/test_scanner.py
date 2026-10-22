from __future__ import annotations

from pathlib import Path

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
    for name in ("main.js", "skip.js", "notes.md"):
        (tmp_path / name).write_bytes('const café = "你好";\r\n'.encode())
    config = CompilationConfig(include_patterns=["*.js"], exclude_patterns=["skip.js"])

    outcome = RepositoryScanner(default_registry(), config).scan(tmp_path)

    assert len(outcome.files) == 1
    assert outcome.files[0].source == 'const café = "你好";\r\n'.encode()
    assert outcome.files[0].size_bytes == len(outcome.files[0].source)
    assert outcome.files[0].candidates == (JavaScriptLanguage,)


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


def test_scanner_respects_gitignore_and_skips_binaries(sample_repo: Path) -> None:
    """Verify `.gitignore` rules and binary files are excluded while valid code is scanned."""
    scanner = RepositoryScanner(default_registry())
    outcome = scanner.scan(sample_repo)

    rel_paths = {f.rel_path for f in outcome.files}

    assert "src/auth/models.py" in rel_paths
    assert "src/auth/jwt_service.py" in rel_paths
    assert "src/api/routes.py" in rel_paths
    assert "src/frontend/client.ts" in rel_paths
    assert "src/utils/helpers.py" in rel_paths

    # Verify gitignored paths and binary assets were excluded
    assert "ignored_dir/skip_me.py" not in rel_paths
    assert "debug.log" not in rel_paths
    assert "assets/logo.dat" not in rel_paths
    assert outcome.binary_files_skipped >= 1
    assert outcome.ignored_files_skipped >= 2


def test_scanner_include_and_exclude_patterns(sample_repo: Path) -> None:
    """Verify user `include_patterns` and `exclude_patterns` filter files accurately."""
    cfg = CompilationConfig(
        include_patterns=["src/**/*.py"],
        exclude_patterns=["**/helpers.py"],
    )
    outcome = RepositoryScanner(default_registry(), cfg).scan(sample_repo)
    rel_paths = {f.rel_path for f in outcome.files}

    assert "src/auth/models.py" in rel_paths
    assert "src/auth/jwt_service.py" in rel_paths
    assert "src/frontend/client.ts" not in rel_paths
    assert "src/utils/helpers.py" not in rel_paths


def test_scanner_raises_on_missing_or_file_path(tmp_path: Path) -> None:
    """Verify `RepositoryNotFoundError` is raised for non-existent or non-directory paths."""
    scanner = RepositoryScanner(default_registry())
    with pytest.raises(RepositoryNotFoundError):
        scanner.scan(tmp_path / "does_not_exist")

    file_target = tmp_path / "single_file.txt"
    file_target.write_text("hello", encoding="utf-8")
    with pytest.raises(RepositoryNotFoundError):
        scanner.scan(file_target)
