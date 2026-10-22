from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.text.extraction import TextExtractor
from contextcraft.languages.text.signatures import SignaturesBuilder
from contextcraft.languages.text.skeleton import SkeletonBuilder


class TextLanguage(Language):
    spec = LanguageSpec(id="text")
    extractor = TextExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
