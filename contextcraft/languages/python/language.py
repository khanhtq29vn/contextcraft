"""Provide Python metadata, source analysis, and cached Tree-sitter queries."""

from __future__ import annotations

from functools import lru_cache

import tree_sitter as ts
import tree_sitter_python

from contextcraft.languages.base import Language
from contextcraft.languages.python.docstrings import extract_docstrings
from contextcraft.languages.python.imports import extract_imports
from contextcraft.languages.python.queries import (
    DOCSTRING_QUERY,
    IMPORT_QUERY,
    SIGS_QUERY,
    SKEL_QUERY,
)
from contextcraft.languages.python.resolution import resolve_imports
from contextcraft.models import File, Import, ImportResolution, ModuleRoot

LANGUAGE_ID = "python"
FILE_EXTENSIONS = frozenset({".py", ".pyi", ".pyw"})
FILENAMES = frozenset({"SConstruct", "SConscript", "wscript"})
ROOT_FILES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "uv.toml",
        "poetry.toml",
        "pdm.toml",
        "hatch.toml",
        "pixi.toml",
        "environment.yml",
        "environment.yaml",
    }
)

PACKAGE_FILES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "MANIFEST.in",
        "uv.toml",
        "uv.lock",
        "poetry.toml",
        "poetry.lock",
        "pdm.toml",
        "pdm.lock",
        "Pipfile",
        "Pipfile.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements.in",
        "requirements-dev.in",
        "constraints.txt",
        "hatch.toml",
        "pixi.toml",
        "pixi.lock",
        "environment.yml",
        "environment.yaml",
        "conda-lock.yml",
        ".python-version",
        ".python-versions",
    }
)

IGNORE_PATTERNS = (
    "**/uv.lock",
    "**/poetry.lock",
    "**/pdm.lock",
    "**/Pipfile.lock",
    "**/pixi.lock",
    "**/conda-lock.yml",
    "**/conda-lock.yaml",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.pytype/**",
    "**/.pyre/**",
    "**/.ruff_cache/**",
    "**/.tox/**",
    "**/.nox/**",
    "**/*.egg-info/**",
    "**/*.egg",
    "**/*.whl",
    "**/.coverage",
    "**/.coverage.*",
    "**/htmlcov/**",
)


@lru_cache(maxsize=1, typed=True)
def get_py_grammar() -> ts.Language:
    """Return the cached Python Tree-sitter grammar."""
    return ts.Language(tree_sitter_python.language())


@lru_cache(maxsize=1, typed=True)
def get_py_import_query() -> ts.Query:
    """Return the cached query for Python import statements."""
    return ts.Query(get_py_grammar(), IMPORT_QUERY)


@lru_cache(maxsize=1, typed=True)
def get_py_docstring_query() -> ts.Query:
    """Return the cached query for module, class, and function docstrings."""
    return ts.Query(get_py_grammar(), DOCSTRING_QUERY)


@lru_cache(maxsize=1, typed=True)
def get_py_skel_query() -> ts.Query:
    """Return the cached query for declaration headers, decorators, and docstrings."""
    return ts.Query(get_py_grammar(), SKEL_QUERY)


@lru_cache(maxsize=1, typed=True)
def get_py_sigs_query() -> ts.Query:
    """Return the cached query for class and function declaration headers."""
    return ts.Query(get_py_grammar(), SIGS_QUERY)


def _render_query(source: bytes, parser: ts.Parser, query: ts.Query) -> str:
    tree = parser.parse(source)
    spans = set()

    for _, captures in ts.QueryCursor(query).matches(tree.root_node):
        if "header.start" in captures:
            start = captures["header.start"][0]
            end = captures["header.end"][0]
            spans.add((start.start_byte, end.start_byte, start.start_point.column))

        for capture in ("doc", "decorator"):
            for node in captures.get(capture, []):
                spans.add((node.start_byte, node.end_byte, node.start_point.column))

    parts = [b" " * column + source[start:end] for start, end, column in sorted(spans)]

    return b"\n".join(parts).decode("utf-8")


class PythonLanguage(Language):
    """Detect Python files, analyze imports and docstrings, and render outlines."""

    @staticmethod
    def get_language_id() -> str:
        """Return the Python language ID."""
        return LANGUAGE_ID

    @staticmethod
    def get_file_extensions() -> frozenset[str]:
        """Return Python source, stub, and windowed-script suffixes."""
        return FILE_EXTENSIONS

    @staticmethod
    def get_filenames() -> frozenset[str]:
        """Return recognized Python build-script filenames."""
        return FILENAMES

    @staticmethod
    def get_root_files() -> frozenset[str]:
        """Return Python project-root marker filenames."""
        return ROOT_FILES

    @staticmethod
    def get_package_files() -> frozenset[str]:
        """Return Python package, dependency, and environment filenames."""
        return PACKAGE_FILES

    @staticmethod
    def get_ignore_patterns() -> tuple[str, ...]:
        """Return exclusion globs for Python locks, caches, and build artifacts."""
        return IGNORE_PATTERNS

    @staticmethod
    def extract_docstrings(source: bytes) -> tuple[str, ...]:
        """Return literal module, class, and function docstrings in source order."""
        return extract_docstrings(
            source, ts.Parser(get_py_grammar()), get_py_docstring_query()
        )

    @staticmethod
    def extract_imports(source: bytes, file_id: int) -> list[Import]:
        """Extract Python imports and associate each one with file_id."""
        return extract_imports(
            source, file_id, ts.Parser(get_py_grammar()), get_py_import_query()
        )

    @staticmethod
    def resolve_imports(
        files: dict[int, File],
        modules: dict[int, ModuleRoot],
        imports: dict[int, Import],
    ) -> list[ImportResolution]:
        """Resolve imports against Python files in their owning project roots.

        Return records sorted by import ID, with definite targets, ambiguous
        files, and unresolved names kept separate. No source is executed.
        """
        return resolve_imports(files, modules, imports)

    @staticmethod
    def render_sigs(input: bytes, parser: ts.Parser | None = None) -> str:
        """Return class and function headers, including nested and private declarations.

        Pass UTF-8 source bytes as input. The supplied parser is reused; if
        omitted, a Python parser is created. The outline omits bodies, decorators,
        and docstrings, so it is not necessarily valid Python.
        """
        parser = parser if parser is not None else ts.Parser(get_py_grammar())

        return _render_query(input, parser, get_py_sigs_query())

    @staticmethod
    def render_skel(source: bytes, parser: ts.Parser | None = None) -> str:
        """Return headers and decorators with captured class and function docstrings.

        Pass UTF-8 bytes as source. The supplied parser is reused; if omitted,
        a Python parser is created. The outline omits imports and implementation
        bodies, so it is not necessarily valid Python.
        """
        parser = parser if parser is not None else ts.Parser(get_py_grammar())

        return _render_query(source, parser, get_py_skel_query())
