"""Language-specific Tree-sitter declaration extraction."""

from __future__ import annotations

from contextcraft.languages.base import LanguageExtractor as LanguageExtractor
from contextcraft.languages.c import CExtractor
from contextcraft.languages.cpp import CppExtractor
from contextcraft.languages.csharp import CSharpExtractor
from contextcraft.languages.css import CSSExtractor
from contextcraft.languages.generic import GenericExtractor
from contextcraft.languages.go import GoExtractor
from contextcraft.languages.html import HTMLExtractor
from contextcraft.languages.java import JavaExtractor
from contextcraft.languages.json import JSONExtractor
from contextcraft.languages.python import PythonExtractor
from contextcraft.languages.rust import RustExtractor
from contextcraft.languages.toml import TOMLExtractor
from contextcraft.languages.typescript import TypeScriptExtractor
from contextcraft.languages.yaml import YAMLExtractor

_TYPESCRIPT = TypeScriptExtractor()
_CSS = CSSExtractor()
_CSHARP = CSharpExtractor()
_GENERIC = GenericExtractor()

_EXTRACTORS: dict[str, LanguageExtractor] = {
    "json": JSONExtractor(),
    "yaml": YAMLExtractor(),
    "toml": TOMLExtractor(),
    "css": _CSS,
    "scss": _CSS,
    "html": HTMLExtractor(),
    "c": CExtractor(),
    "cpp": CppExtractor(),
    "csharp": _CSHARP,
    "c_sharp": _CSHARP,
    "java": JavaExtractor(),
    "python": PythonExtractor(),
    "javascript": _TYPESCRIPT,
    "typescript": _TYPESCRIPT,
    "tsx": _TYPESCRIPT,
    "rust": RustExtractor(),
    "go": GoExtractor(),
}


def get_extractor(language_id: str) -> LanguageExtractor:
    return _EXTRACTORS.get(language_id, _GENERIC)
