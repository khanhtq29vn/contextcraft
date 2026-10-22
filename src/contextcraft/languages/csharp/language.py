from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.csharp.extraction import CSharpExtractor
from contextcraft.languages.csharp.signatures import SignaturesBuilder
from contextcraft.languages.csharp.skeleton import SkeletonBuilder


class CSharpLanguage(Language):
    spec = LanguageSpec(
        id="csharp",
        parser_id="csharp",
        aliases=("c_sharp",),
        extensions=frozenset({".cs"}),
        ignore_patterns=("bin/", "obj/"),
    )
    extractor = CSharpExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
