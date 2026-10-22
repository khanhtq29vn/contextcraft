from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.cpp.extraction import CppExtractor
from contextcraft.languages.cpp.signatures import SignaturesBuilder
from contextcraft.languages.cpp.skeleton import SkeletonBuilder


class CppLanguage(Language):
    spec = LanguageSpec(
        id="cpp",
        parser_id="cpp",
        extensions=frozenset({".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".hxx"}),
        ignore_patterns=("*.o", "*.a"),
    )
    extractor = CppExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
