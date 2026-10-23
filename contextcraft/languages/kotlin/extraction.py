from __future__ import annotations

import re
from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class KotlinRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "object_declaration": "class",
        "function_declaration": "function",
        "secondary_constructor": "method",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["import_header"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type in {"type_identifier", "simple_identifier"}
            ),
            None,
        )

    def body_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type in {"class_body", "function_body"}
            ),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return (
            self.node_range(body)
            if node.type == "function_declaration" and body is not None
            else None
        )

    def is_reference(self, node: Node) -> bool:
        return node.type in {"simple_identifier", "type_identifier"}

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return not re.search(
            rb"\bprivate\b", source[node.start_byte : (self.body_node(node) or node).start_byte]
        )


class KotlinExtractor(StructuralExtractor):
    rules = KotlinRules
