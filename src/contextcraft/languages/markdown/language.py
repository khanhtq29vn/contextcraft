from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.markdown.extraction import MarkdownExtractor
from contextcraft.languages.markdown.signatures import SignaturesBuilder
from contextcraft.languages.markdown.skeleton import SkeletonBuilder


class MarkdownLanguage(Language):
    spec = LanguageSpec(
        id="markdown",
        parser_id="markdown",
        extensions=frozenset({".md", ".mdx"}),
    )
    extractor = MarkdownExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
