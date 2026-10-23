from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.scss.extraction import SCSSExtractor
from contextcraft.languages.scss.signatures import SignaturesBuilder
from contextcraft.languages.scss.skeleton import SkeletonBuilder


class SCSSLanguage(Language):
    spec = LanguageSpec(
        id="scss",
        parser_id="scss",
        extensions=frozenset({".scss"}),
    )
    extractor = SCSSExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
