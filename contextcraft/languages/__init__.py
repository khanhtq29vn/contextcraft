"""Register the built-in language implementations used by pipeline stages."""

from __future__ import annotations

from contextcraft.languages.python.language import PythonLanguage

BUILTIN_LANGUAGES = (PythonLanguage,)
