from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast import ParsedAst
from contextcraft.languages.base import Language


def parse(source: bytes, language: type[Language]) -> ParsedAst:
    if language.spec.parser_id is None:
        return ParsedAst(source=source)
    try:
        parser = get_parser(language.spec.parser_id)
    except Exception:
        return ParsedAst(source=source, has_errors=True)
    root = parser.parse(source).root_node
    return language.parse(root, source)
