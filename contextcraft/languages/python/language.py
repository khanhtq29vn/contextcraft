from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.python.extraction import PythonExtractor
from contextcraft.languages.python.signatures import SignaturesBuilder
from contextcraft.languages.python.skeleton import SkeletonBuilder


class PythonLanguage(Language):
    spec = LanguageSpec(
        id="python",
        parser_id="python",
        extensions=frozenset({".py", ".pyi"}),
        ignore_patterns=(
            "*.pyc",
            "*.pyo",
            ".venv/",
            "venv/",
            "__pycache__/",
            ".mypy_cache/",
            ".pytest_cache/",
            ".ruff_cache/",
            ".hypothesis/",
            "*.egg-info/",
            ".coverage*",
            "htmlcov/",
            ".tox/",
            ".nox/",
            "uv.lock",
            "poetry.lock",
            "Pipfile.lock",
        ),
    )
    extractor = PythonExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
