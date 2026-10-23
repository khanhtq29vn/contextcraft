from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.toml.extraction import TOMLExtractor
from contextcraft.languages.toml.signatures import SignaturesBuilder
from contextcraft.languages.toml.skeleton import SkeletonBuilder


class TOMLLanguage(Language):
    spec = LanguageSpec(
        id="toml",
        parser_id="toml",
        extensions=frozenset({".toml"}),
    )
    extractor = TOMLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
