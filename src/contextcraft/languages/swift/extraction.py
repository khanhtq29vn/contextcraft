from __future__ import annotations

import re
from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class SwiftRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "protocol_declaration": "interface",
        "function_declaration": "function",
        "init_declaration": "method",
        "deinit_declaration": "method",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["import_declaration"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "class_declaration":
            declaration_kind = node.child_by_field_name("declaration_kind")
            if declaration_kind is not None and declaration_kind.type in {"struct", "enum"}:
                return declaration_kind.type
        return super().symbol_kind(node, parent_type)

    def name_node(self, node: Node) -> Node | None:
        if node.type == "deinit_declaration":
            return next((child for child in node.children if child.type == "deinit"), None)
        return node.child_by_field_name("name") or next(
            (
                child
                for child in node.named_children
                if child.type in {"type_identifier", "simple_identifier"}
            ),
            None,
        )

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body") or next(
            (
                child
                for child in node.named_children
                if child.type in {"class_body", "protocol_body", "function_body"}
            ),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type in {"function_declaration", "init_declaration", "deinit_declaration"}:
            return self.brace_body_range(self.body_node(node), source)
        return None

    def is_reference(self, node: Node) -> bool:
        return node.type in {"simple_identifier", "type_identifier"}

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return not re.search(
            rb"\b(?:private|fileprivate)\b",
            source[node.start_byte : (self.body_node(node) or node).start_byte],
        )


class SwiftExtractor(StructuralExtractor):
    rules = SwiftRules
