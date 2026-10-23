from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.zig.extraction import ZigExtractor
from contextcraft.languages.zig.signatures import SignaturesBuilder
from contextcraft.languages.zig.skeleton import SkeletonBuilder


class ZigLanguage(Language):
    spec = LanguageSpec(
        id="zig",
        parser_id="zig",
        extensions=frozenset({".zig"}),
        ignore_patterns=(".zig-cache/", "zig-cache/", "zig-out/"),
    )
    extractor = ZigExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
