from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.go.extraction import GoExtractor
from contextcraft.languages.go.signatures import SignaturesBuilder
from contextcraft.languages.go.skeleton import SkeletonBuilder


class GoLanguage(Language):
    spec = LanguageSpec(
        id="go",
        parser_id="go",
        extensions=frozenset({".go"}),
        ignore_patterns=("vendor/", "go.sum"),
    )
    extractor = GoExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
