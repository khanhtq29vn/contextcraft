from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pathspec

from contextcraft.languages.base import Language
from contextcraft.languages.registry import LanguageRegistry
from contextcraft.models import CompilationConfig, RepositoryNotFoundError


@dataclass(frozen=True)
class ScannedFile:
    rel_path: str
    abs_path: str
    size_bytes: int
    source: bytes
    candidates: tuple[type[Language], ...]


@dataclass(frozen=True)
class ScanOutcome:
    root_path: Path
    files: list[ScannedFile]
    total_files_discovered: int
    binary_files_skipped: int
    ignored_files_skipped: int


class RepositoryScanner:
    _DEFAULT_IGNORE_PATTERNS: ClassVar[tuple[str, ...]] = (
        ".git/",
        ".hg/",
        ".svn/",
        ".idea/",
        ".vscode/",
        ".contextcraft_cache/",
        ".DS_Store",
        "Thumbs.db",
    )
    _IGNORE_FILENAMES: ClassVar[tuple[str, ...]] = (
        ".gitignore",
        ".ignore",
        ".contextignore",
        ".repomixignore",
    )

    def __init__(self, registry: LanguageRegistry, config: CompilationConfig | None = None) -> None:
        self.registry = registry
        self.config = config if config is not None else CompilationConfig()

    def scan(self, root_path: str | Path) -> ScanOutcome:
        root = Path(root_path).expanduser().resolve()
        if not root.is_dir():
            raise RepositoryNotFoundError(f"Repository path must be an existing directory: {root}")

        patterns = [*self._DEFAULT_IGNORE_PATTERNS, *self.registry.ignore_patterns]
        git_exclude = root / ".git" / "info" / "exclude"
        if self.config.respect_gitignore and not (root / ".git").is_symlink():
            patterns.extend(self._read_ignore(git_exclude, ""))
        inherited: dict[Path, list[str]] = {root: patterns}
        specs: dict[tuple[str, ...], pathspec.PathSpec[Any]] = {}
        include = pathspec.PathSpec.from_lines("gitignore", self.config.include_patterns)
        found: list[ScannedFile] = []
        discovered = binary = ignored = 0

        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            directory = Path(current)
            prefix = directory.relative_to(root).as_posix()
            if prefix == ".":
                prefix = ""
            rules = list(inherited.pop(directory))
            if self.config.respect_gitignore:
                for name in self._IGNORE_FILENAMES:
                    rules.extend(self._read_ignore(directory / name, prefix))
            key = (*rules, *self.config.exclude_patterns)
            if key not in specs:
                specs[key] = pathspec.PathSpec.from_lines("gitignore", key)
            spec = specs[key]

            kept = []
            for name in sorted(dirs):
                child = directory / name
                rel = child.relative_to(root).as_posix()
                if (
                    child.is_symlink()
                    or name in {".git", ".hg", ".svn"}
                    or spec.match_file(rel + "/")
                ):
                    ignored += 1
                    continue
                kept.append(name)
                inherited[child] = rules
            dirs[:] = kept

            for name in sorted(files):
                discovered += 1
                path = directory / name
                rel = path.relative_to(root).as_posix()
                if (
                    name in self._IGNORE_FILENAMES
                    or path.is_symlink()
                    or spec.match_file(rel)
                    or (self.config.include_patterns and not include.match_file(rel))
                ):
                    ignored += 1
                    continue
                try:
                    info = path.stat()
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_size > self.config.max_file_size_bytes
                    ):
                        ignored += 1
                        continue
                    with path.open("rb") as stream:
                        source = stream.read(self.config.max_file_size_bytes + 1)
                except OSError:
                    ignored += 1
                    continue
                if not source or len(source) > self.config.max_file_size_bytes:
                    ignored += 1
                    continue
                if self._is_binary_bytes(source[:8192]):
                    binary += 1
                    continue
                try:
                    source.decode("utf-8")
                except UnicodeDecodeError:
                    binary += 1
                    continue
                found.append(
                    ScannedFile(
                        rel,
                        str(path),
                        len(source),
                        source,
                        tuple(self.registry.detect_candidates(rel)),
                    )
                )

        found.sort(key=lambda item: item.rel_path)
        return ScanOutcome(root, found, discovered, binary, ignored)

    @staticmethod
    def _read_ignore(path: Path, prefix: str) -> list[str]:
        if path.is_symlink():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return []
        if not prefix:
            return lines
        scoped = []
        for line in lines:
            if not line or line.startswith("#"):
                continue
            negation = "!" if line.startswith("!") else ""
            rule = line[len(negation) :]
            if rule.startswith("/") or "/" in rule.rstrip("/"):
                rule = f"{prefix}/{rule.lstrip('/')}"
            else:
                rule = f"{prefix}/**/{rule}"
            scoped.append(negation + rule)
        return scoped

    @staticmethod
    def _is_binary_bytes(sample: bytes) -> bool:
        if not sample:
            return False
        if b"\x00" in sample:
            return True
        controls = sum(byte < 32 and byte not in (9, 10, 12, 13, 27) for byte in sample)
        return controls / len(sample) > 0.30
