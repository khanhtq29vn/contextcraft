from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.javascript.extraction import JavaScriptExtractor
from contextcraft.languages.javascript.signatures import SignaturesBuilder
from contextcraft.languages.javascript.skeleton import SkeletonBuilder


class JavaScriptLanguage(Language):
    spec = LanguageSpec(
        id="javascript",
        extensions=frozenset(
            {
                ".js",
                ".mjs",
                ".cjs",
                ".jsx",
            }
        ),
        ignore_patterns=(
            "node_modules/",
            "dist/",
        ),
        parser_id="javascript",
    )
    extractor = JavaScriptExtractor

    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
