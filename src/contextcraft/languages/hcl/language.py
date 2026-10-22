from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.hcl.extraction import HCLExtractor
from contextcraft.languages.hcl.signatures import SignaturesBuilder
from contextcraft.languages.hcl.skeleton import SkeletonBuilder


class HCLLanguage(Language):
    spec = LanguageSpec(
        id="hcl",
        parser_id="hcl",
        extensions=frozenset({".tf", ".hcl", ".tfvars"}),
        ignore_patterns=(".terraform/",),
    )
    extractor = HCLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
