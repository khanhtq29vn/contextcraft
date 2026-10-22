from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.cmake.extraction import CMakeExtractor
from contextcraft.languages.cmake.signatures import SignaturesBuilder
from contextcraft.languages.cmake.skeleton import SkeletonBuilder


class CMakeLanguage(Language):
    spec = LanguageSpec(
        id="cmake",
        parser_id="cmake",
        extensions=frozenset({".cmake"}),
        filenames=frozenset({"CMakeLists.txt"}),
        ignore_patterns=("CMakeFiles/", "CMakeCache.txt"),
    )
    extractor = CMakeExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
