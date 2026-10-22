from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.protobuf.extraction import ProtobufExtractor
from contextcraft.languages.protobuf.signatures import SignaturesBuilder
from contextcraft.languages.protobuf.skeleton import SkeletonBuilder


class ProtobufLanguage(Language):
    spec = LanguageSpec(
        id="protobuf",
        parser_id="proto",
        aliases=("proto",),
        extensions=frozenset({".proto"}),
    )
    extractor = ProtobufExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
