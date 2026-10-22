from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.r.extraction import RExtractor
from contextcraft.languages.r.signatures import SignaturesBuilder
from contextcraft.languages.r.skeleton import SkeletonBuilder


class RLanguage(Language):
    spec = LanguageSpec(
        id="r",
        parser_id="r",
        extensions=frozenset({".r", ".R"}),
    )
    extractor = RExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
