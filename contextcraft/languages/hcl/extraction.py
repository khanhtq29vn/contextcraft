from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class HCLRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"block": "block"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset([])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "identifier"), None)

    def symbol_name(self, node: Node, source: bytes) -> str | None:
        labels = [
            source[child.start_byte : child.end_byte].decode("utf-8").strip('"')
            for child in node.named_children
            if child.type in {"identifier", "string_lit"}
        ]
        return ".".join(labels) or None

    def body_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "body"), None)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        return None


class HCLExtractor(StructuralExtractor):
    rules = HCLRules
