from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.c.extraction import CExtractor
from contextcraft.languages.c.signatures import SignaturesBuilder
from contextcraft.languages.c.skeleton import SkeletonBuilder


class CLanguage(Language):
    spec = LanguageSpec(
        id="c",
        parser_id="c",
        extensions=frozenset({".c", ".h"}),
        ignore_patterns=("*.o", "*.a"),
    )
    extractor = CExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
