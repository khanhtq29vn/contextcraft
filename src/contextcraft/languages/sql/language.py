from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.sql.extraction import SQLExtractor
from contextcraft.languages.sql.signatures import SignaturesBuilder
from contextcraft.languages.sql.skeleton import SkeletonBuilder


class SQLLanguage(Language):
    spec = LanguageSpec(
        id="sql",
        parser_id="sql",
        extensions=frozenset({".sql"}),
    )
    extractor = SQLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
