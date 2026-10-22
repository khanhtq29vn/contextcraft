from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.json.extraction import JSONExtractor
from contextcraft.languages.json.signatures import SignaturesBuilder
from contextcraft.languages.json.skeleton import SkeletonBuilder


class JSONLanguage(Language):
    spec = LanguageSpec(
        id="json",
        parser_id="json",
        extensions=frozenset({".json"}),
    )
    extractor = JSONExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
