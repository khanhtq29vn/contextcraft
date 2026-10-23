from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.rst.extraction import RSTExtractor
from contextcraft.languages.rst.signatures import SignaturesBuilder
from contextcraft.languages.rst.skeleton import SkeletonBuilder


class RSTLanguage(Language):
    spec = LanguageSpec(
        id="rst",
        parser_id="rst",
        extensions=frozenset({".rst"}),
    )
    extractor = RSTExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
