"""Provide Python metadata, source analysis, and cached Tree-sitter queries."""

from __future__ import annotations

from functools import lru_cache

import tree_sitter as ts
import tree_sitter_python

from contextcraft.languages.base import Language
from contextcraft.languages.python.docstrings import extract_docstrings
from contextcraft.languages.python.imports import extract_imports
from contextcraft.languages.python.queries import ANALYSIS_QUERY
from contextcraft.languages.python.resolution import resolve_imports
from contextcraft.models import File, FileAnalysis, Import, ImportResolution, ModuleRoot

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
def get_py_analysis_query() -> ts.Query:
    """Return the combined query for metadata and both outlines."""
    return ts.Query(get_py_grammar(), ANALYSIS_QUERY)


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
    def analyze(source: bytes, file_id: int) -> FileAnalysis:
        """Parse once and extract metadata and outline spans with one query pass."""
        tree = ts.Parser(get_py_grammar()).parse(source)
        captures_by_name: dict[str, list[ts.Node]] = {}
        signatures = set()
        skeleton = set()

        for _, captures in ts.QueryCursor(get_py_analysis_query()).matches(
            tree.root_node
        ):
            if "header.start" in captures:
                start = captures["header.start"][0]
                end = captures["header.end"][0]
                span = (start.start_byte, end.start_byte, start.start_point.column)
                signatures.add(span)
                body = start.child_by_field_name("body")

                # SKEL requires a block; SIGS also accepts incomplete declarations.
                if body is not None and body.type == "block":
                    skeleton.add(span)

            for name in ("docstring", "import.statement"):
                captures_by_name.setdefault(name, []).extend(captures.get(name, []))

            for name in ("decorator", "skel.doc"):
                for node in captures.get(name, []):
                    skeleton.add(
                        (node.start_byte, node.end_byte, node.start_point.column)
                    )

        return FileAnalysis(
            docstrings=extract_docstrings(
                source, captures_by_name.get("docstring", [])
            ),
            imports=tuple(
                extract_imports(
                    source, file_id, captures_by_name.get("import.statement", [])
                )
            ),
            sigs=tuple(sorted(signatures)),
            skel=tuple(sorted(skeleton)),
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
