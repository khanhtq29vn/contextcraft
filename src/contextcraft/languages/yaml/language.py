from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.yaml.extraction import YAMLExtractor
from contextcraft.languages.yaml.signatures import SignaturesBuilder
from contextcraft.languages.yaml.skeleton import SkeletonBuilder


class YAMLLanguage(Language):
    spec = LanguageSpec(
        id="yaml",
        parser_id="yaml",
        extensions=frozenset({".yaml", ".yml"}),
    )
    extractor = YAMLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
