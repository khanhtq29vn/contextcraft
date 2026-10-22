from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.java.extraction import JavaExtractor
from contextcraft.languages.java.signatures import SignaturesBuilder
from contextcraft.languages.java.skeleton import SkeletonBuilder


class JavaLanguage(Language):
    spec = LanguageSpec(
        id="java",
        parser_id="java",
        extensions=frozenset({".java"}),
        ignore_patterns=("target/", "*.class", "*.jar"),
    )
    extractor = JavaExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
