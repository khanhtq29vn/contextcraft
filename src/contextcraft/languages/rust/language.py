from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.rust.extraction import RustExtractor
from contextcraft.languages.rust.signatures import SignaturesBuilder
from contextcraft.languages.rust.skeleton import SkeletonBuilder


class RustLanguage(Language):
    spec = LanguageSpec(
        id="rust",
        parser_id="rust",
        extensions=frozenset({".rs"}),
        ignore_patterns=("target/", "Cargo.lock"),
    )
    extractor = RustExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
