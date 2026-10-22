from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.tsx.extraction import TSXExtractor
from contextcraft.languages.tsx.signatures import SignaturesBuilder
from contextcraft.languages.tsx.skeleton import SkeletonBuilder


class TSXLanguage(Language):
    spec = LanguageSpec(
        id="tsx",
        parser_id="tsx",
        extensions=frozenset({".tsx"}),
        ignore_patterns=("node_modules/", "dist/"),
    )
    extractor = TSXExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
