from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.scala.extraction import ScalaExtractor
from contextcraft.languages.scala.signatures import SignaturesBuilder
from contextcraft.languages.scala.skeleton import SkeletonBuilder


class ScalaLanguage(Language):
    spec = LanguageSpec(
        id="scala",
        parser_id="scala",
        extensions=frozenset({".scala"}),
        ignore_patterns=("target/",),
    )
    extractor = ScalaExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
