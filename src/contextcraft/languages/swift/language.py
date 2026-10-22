from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.swift.extraction import SwiftExtractor
from contextcraft.languages.swift.signatures import SignaturesBuilder
from contextcraft.languages.swift.skeleton import SkeletonBuilder


class SwiftLanguage(Language):
    spec = LanguageSpec(
        id="swift",
        parser_id="swift",
        extensions=frozenset({".swift"}),
        ignore_patterns=(".build/",),
    )
    extractor = SwiftExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
