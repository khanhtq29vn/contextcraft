from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.typescript.extraction import TypeScriptExtractor
from contextcraft.languages.typescript.signatures import SignaturesBuilder
from contextcraft.languages.typescript.skeleton import SkeletonBuilder


class TypeScriptLanguage(Language):
    spec = LanguageSpec(
        id="typescript",
        parser_id="typescript",
        extensions=frozenset({".ts", ".cts", ".mts"}),
        ignore_patterns=(
            "node_modules/",
            "dist/",
            "*.min.js",
            "*.map",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lockb",
        ),
    )
    extractor = TypeScriptExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
