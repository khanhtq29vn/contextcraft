from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.make.extraction import MakefileExtractor
from contextcraft.languages.make.signatures import SignaturesBuilder
from contextcraft.languages.make.skeleton import SkeletonBuilder


class MakefileLanguage(Language):
    spec = LanguageSpec(
        id="make",
        parser_id="make",
        filenames=frozenset({"Makefile", "makefile", "justfile"}),
    )
    extractor = MakefileExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
