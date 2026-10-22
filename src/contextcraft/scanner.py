"""Multi-layered repository file scanner with hierarchical ignore rules.

Inspired by `yamadashy/repomix`'s file discovery architecture, this module
traverses a repository while respecting:
1. Built-in default exclusions (VCS directories, virtualenvs, build artifacts, lockfiles)
2. Hierarchical `.gitignore`, `.ignore`, and `.contextignore` control files
3. `.git/info/exclude` rules
4. User-configured `include_patterns` and `exclude_patterns`
5. Fast binary stream heuristics and file-size guardrails
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pathspec

from contextcraft.models import CompilationConfig, RepositoryNotFoundError


@dataclass(frozen=True, slots=True)
class ScannedFile:
    """Represents a validated UTF-8 text file discovered in the repository."""

    rel_path: str
    abs_path: str
    language: str
    size_bytes: int
    raw_content: str


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    """Aggregated result of scanning a repository workspace."""

    root_path: Path
    files: list[ScannedFile]
    total_files_discovered: int
    binary_files_skipped: int
    ignored_files_skipped: int


class RepositoryScanner:
    """High-speed, gitignore-aware repository scanner and language classifier."""

    DEFAULT_IGNORED_DIRS: ClassVar[frozenset[str]] = frozenset(
        {
            ".git",
            ".hg",
            ".svn",
            "node_modules",
            ".venv",
            "venv",
            "env",
            "ENV",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".nox",
            ".hypothesis",
            "dist",
            "build",
            "out",
            "target",
            "vendor",
            ".next",
            ".nuxt",
            ".svelte-kit",
            ".turbo",
            ".vercel",
            "coverage",
            "htmlcov",
            "site",
            ".idea",
            ".vscode",
            ".contextcraft_cache",
            "eggs",
            ".eggs",
        }
    )

    DEFAULT_IGNORED_FILES: ClassVar[frozenset[str]] = frozenset(
        {
            ".DS_Store",
            "Thumbs.db",
            "uv.lock",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lockb",
            "Cargo.lock",
            "poetry.lock",
            "Pipfile.lock",
            "Gemfile.lock",
            "composer.lock",
            "go.sum",
            "contextcraft_reference_bundle.xml",
            "agentscaffold_reference_bundle.xml",
        }
    )

    DEFAULT_IGNORED_GLOBS: ClassVar[tuple[str, ...]] = (
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.dll",
        "*.dylib",
        "*.exe",
        "*.bin",
        "*.o",
        "*.a",
        "*.lib",
        "*.class",
        "*.jar",
        "*.war",
        "*.ear",
        "*.zip",
        "*.tar",
        "*.tar.gz",
        "*.tgz",
        "*.rar",
        "*.7z",
        "*.gz",
        "*.bz2",
        "*.xz",
        "*.pdf",
        "*.doc",
        "*.docx",
        "*.xls",
        "*.xlsx",
        "*.ppt",
        "*.pptx",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.webp",
        "*.bmp",
        "*.ico",
        "*.svg",
        "*.mp3",
        "*.mp4",
        "*.wav",
        "*.avi",
        "*.mov",
        "*.woff",
        "*.woff2",
        "*.ttf",
        "*.eot",
        "*.otf",
        "*.min.js",
        "*.min.css",
        "*.bundle.js",
        "*.chunk.js",
        "*.map",
        "*.sqlite",
        "*.sqlite3",
        "*.db",
        "*.parquet",
        "*.feather",
        "*.pt",
        "*.pth",
        "*.onnx",
        "*.safetensors",
        "*.gguf",
        "*.egg-info/**",
        ".aider.tags.cache*",
    )

    IGNORE_CONTROL_FILES: ClassVar[tuple[str, ...]] = (
        ".gitignore",
        ".ignore",
        ".contextignore",
        ".repomixignore",
    )

    EXTENSION_LANGUAGE_MAP: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".ts": "typescript",
        ".cts": "typescript",
        ".mts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".cjs": "javascript",
        ".mjs": "javascript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".scala": "scala",
        ".lua": "lua",
        ".r": "r",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
        ".md": "markdown",
        ".mdx": "markdown",
        ".rst": "rst",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "scss",
        ".proto": "protobuf",
        ".graphql": "graphql",
        ".gql": "graphql",
        ".tf": "hcl",
    }

    FILENAME_LANGUAGE_MAP: ClassVar[dict[str, str]] = {
        "dockerfile": "dockerfile",
        "makefile": "makefile",
        "cmakelists.txt": "cmake",
        "justfile": "makefile",
    }

    def __init__(self, config: CompilationConfig | None = None) -> None:
        """Initialize the scanner with compilation configuration."""
        self.config = config or CompilationConfig()

    def scan(self, root_path: str | Path) -> ScanOutcome:
        """Traverse `root_path` and return all non-ignored, valid text files."""
        resolved_root = Path(root_path).expanduser().resolve()
        if not resolved_root.exists():
            raise RepositoryNotFoundError(f"Repository path does not exist: {resolved_root}")
        if not resolved_root.is_dir():
            raise RepositoryNotFoundError(
                f"Repository path must be a directory, got file: {resolved_root}"
            )

        ignore_spec = self._build_ignore_spec(resolved_root)
        include_spec = (
            pathspec.PathSpec.from_lines("gitignore", self.config.include_patterns)
            if self.config.include_patterns
            else None
        )

        scanned_files: list[ScannedFile] = []
        total_discovered = 0
        binary_skipped = 0
        ignored_skipped = 0

        for current_root, dirs, files in os.walk(resolved_root, topdown=True, followlinks=False):
            current_dir_path = Path(current_root)
            rel_dir = self._to_posix_relpath(current_dir_path, resolved_root)

            # Prune ignored directories in-place for fast traversal
            kept_dirs: list[str] = []
            for d in sorted(dirs):
                if d in self.DEFAULT_IGNORED_DIRS or d.endswith(".egg-info"):
                    ignored_skipped += 1
                    continue
                dir_rel_posix = f"{rel_dir}/{d}" if rel_dir else d
                if ignore_spec.match_file(dir_rel_posix) or ignore_spec.match_file(
                    f"{dir_rel_posix}/"
                ):
                    ignored_skipped += 1
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            for fname in sorted(files):
                total_discovered += 1
                if fname in self.DEFAULT_IGNORED_FILES or fname in self.IGNORE_CONTROL_FILES:
                    ignored_skipped += 1
                    continue

                file_path = current_dir_path / fname
                if file_path.is_symlink():
                    ignored_skipped += 1
                    continue

                rel_file_posix = f"{rel_dir}/{fname}" if rel_dir else fname

                # Check ignore patterns
                if ignore_spec.match_file(rel_file_posix):
                    ignored_skipped += 1
                    continue

                # Check explicit include patterns if configured
                if include_spec is not None and not include_spec.match_file(rel_file_posix):
                    ignored_skipped += 1
                    continue

                try:
                    stat_info = file_path.stat()
                except OSError:
                    ignored_skipped += 1
                    continue

                if stat_info.st_size == 0 or stat_info.st_size > self.config.max_file_size_bytes:
                    ignored_skipped += 1
                    continue

                raw_text = self._read_text_if_not_binary(file_path)
                if raw_text is None:
                    binary_skipped += 1
                    continue

                language = self.detect_language(file_path)
                scanned_files.append(
                    ScannedFile(
                        rel_path=rel_file_posix,
                        abs_path=str(file_path),
                        language=language,
                        size_bytes=stat_info.st_size,
                        raw_content=raw_text,
                    )
                )

        scanned_files.sort(key=lambda item: item.rel_path)
        return ScanOutcome(
            root_path=resolved_root,
            files=scanned_files,
            total_files_discovered=total_discovered,
            binary_files_skipped=binary_skipped,
            ignored_files_skipped=ignored_skipped,
        )

    def _build_ignore_spec(self, root_path: Path) -> pathspec.PathSpec[Any]:
        """Collect default, `.gitignore`, `.contextignore`, and custom ignore rules."""
        patterns: list[str] = list(self.DEFAULT_IGNORED_GLOBS)
        patterns.extend(self.config.exclude_patterns)

        if self.config.respect_gitignore:
            # 1. Read .git/info/exclude if present
            git_exclude = root_path / ".git" / "info" / "exclude"
            if git_exclude.is_file():
                patterns.extend(self._read_ignore_lines(git_exclude, prefix=""))

            # 2. Walk repository for hierarchical ignore control files
            for current_root, dirs, files in os.walk(root_path, topdown=True, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in self.DEFAULT_IGNORED_DIRS and not d.endswith(".egg-info")
                ]
                current_dir = Path(current_root)
                rel_dir = self._to_posix_relpath(current_dir, root_path)

                for control_name in self.IGNORE_CONTROL_FILES:
                    if control_name in files:
                        control_path = current_dir / control_name
                        patterns.extend(self._read_ignore_lines(control_path, prefix=rel_dir))

        return pathspec.PathSpec.from_lines("gitignore", patterns)

    @classmethod
    def _read_ignore_lines(cls, ignore_file: Path, prefix: str) -> list[str]:
        """Parse an ignore file and scope its rules to `prefix` directory if nested."""
        scoped_lines: list[str] = []
        try:
            content = ignore_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return scoped_lines

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if not prefix:
                scoped_lines.append(line)
                continue

            is_negated = line.startswith("!")
            clean_rule = line[1:] if is_negated else line
            clean_rule = clean_rule.lstrip("/")

            scoped_rule = f"{prefix}/{clean_rule}"
            if is_negated:
                scoped_rule = f"!{scoped_rule}"
            scoped_lines.append(scoped_rule)

        return scoped_lines

    @classmethod
    def _read_text_if_not_binary(cls, file_path: Path) -> str | None:
        """Read file as UTF-8 text, returning None if binary bytes are detected."""
        try:
            with file_path.open("rb") as fh:
                head = fh.read(8192)
                if cls.is_binary_bytes(head):
                    return None
                remainder = fh.read()
        except OSError:
            return None

        full_bytes = head + remainder
        try:
            return full_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return full_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                return None

    @staticmethod
    def is_binary_bytes(sample: bytes) -> bool:
        """Fast heuristic to detect binary buffers via null bytes and control characters."""
        if not sample:
            return False
        if b"\x00" in sample:
            return True

        # Count non-printable ASCII control bytes (excluding tab, newline, carriage return, formfeed)
        control_bytes = sum(
            1 for b in sample if b < 32 and b not in (9, 10, 12, 13, 27)
        )
        return (control_bytes / len(sample)) > 0.30

    @classmethod
    def detect_language(cls, file_path: str | Path) -> str:
        """Map a file path to its canonical language identifier."""
        path_obj = Path(file_path)
        lower_name = path_obj.name.lower()
        if lower_name in cls.FILENAME_LANGUAGE_MAP:
            return cls.FILENAME_LANGUAGE_MAP[lower_name]

        ext = path_obj.suffix.lower()
        return cls.EXTENSION_LANGUAGE_MAP.get(ext, "unknown")

    @staticmethod
    def _to_posix_relpath(target: Path, root: Path) -> str:
        """Return POSIX relative path without leading './'."""
        if target == root:
            return ""
        rel = target.relative_to(root).as_posix()
        return "" if rel == "." else rel
