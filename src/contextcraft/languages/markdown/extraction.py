from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class MarkdownRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"atx_heading": "heading", "setext_heading": "heading"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset([])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("heading_content") or next(
            (child for child in node.named_children if child.type == "inline"), None
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        return None

    def is_reference(self, node: Node) -> bool:
        return False


class MarkdownExtractor(StructuralExtractor):
    rules = MarkdownRules
