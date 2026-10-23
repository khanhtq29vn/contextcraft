from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.kotlin.extraction import KotlinExtractor
from contextcraft.languages.kotlin.signatures import SignaturesBuilder
from contextcraft.languages.kotlin.skeleton import SkeletonBuilder


class KotlinLanguage(Language):
    spec = LanguageSpec(
        id="kotlin",
        parser_id="kotlin",
        extensions=frozenset({".kt", ".kts"}),
        ignore_patterns=(".gradle/", "build/"),
    )
    extractor = KotlinExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
