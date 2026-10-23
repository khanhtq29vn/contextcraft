from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.html.extraction import HTMLExtractor
from contextcraft.languages.html.signatures import SignaturesBuilder
from contextcraft.languages.html.skeleton import SkeletonBuilder


class HTMLLanguage(Language):
    spec = LanguageSpec(
        id="html",
        parser_id="html",
        extensions=frozenset({".html", ".htm"}),
    )
    extractor = HTMLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
