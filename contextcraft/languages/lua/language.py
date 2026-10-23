from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.lua.extraction import LuaExtractor
from contextcraft.languages.lua.signatures import SignaturesBuilder
from contextcraft.languages.lua.skeleton import SkeletonBuilder


class LuaLanguage(Language):
    spec = LanguageSpec(
        id="lua",
        parser_id="lua",
        extensions=frozenset({".lua"}),
    )
    extractor = LuaExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
