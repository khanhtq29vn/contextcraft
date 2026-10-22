from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.css.extraction import CSSExtractor
from contextcraft.languages.css.signatures import SignaturesBuilder
from contextcraft.languages.css.skeleton import SkeletonBuilder


class CSSLanguage(Language):
    spec = LanguageSpec(
        id="css",
        parser_id="css",
        extensions=frozenset({".css"}),
        ignore_patterns=("*.min.css",),
    )
    extractor = CSSExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
