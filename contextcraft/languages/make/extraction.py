from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class MakefileRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"rule": "target"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["include_directive"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "targets"), None)

    def body_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "recipe"), None)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return self.node_range(body) if body is not None else None

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        filenames = node.child_by_field_name("filenames")
        if filenames is None:
            return []
        return [
            source[child.start_byte : child.end_byte].decode("utf-8")
            for child in filenames.named_children
            if child.type == "word"
        ]

    def is_reference(self, node: Node) -> bool:
        return node.type == "variable_reference"


class MakefileExtractor(StructuralExtractor):
    rules = MakefileRules
