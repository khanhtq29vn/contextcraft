from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class RubyRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class": "class",
        "module": "module",
        "method": "method",
        "singleton_method": "method",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["call"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        parent = outer_node.parent
        if (
            parent is not None
            and parent.type == "body_statement"
            and parent.named_children
            and parent.named_children[0] == outer_node
        ):
            return super().extract_docstring(node, parent, source)
        return super().extract_docstring(node, outer_node, source)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return (
            self.node_range(body)
            if node.type in {"method", "singleton_method"} and body is not None
            else None
        )

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        method = node.child_by_field_name("method")
        if method is None or method.text not in {b"require", b"require_relative", b"load"}:
            return []
        arguments = node.child_by_field_name("arguments")
        if arguments is None:
            return []
        return [
            source[child.start_byte + 1 : child.end_byte - 1].decode("utf-8")
            for child in arguments.named_children
            if child.type == "string"
            and not any(part.type == "interpolation" for part in child.named_children)
        ]

    def is_reference(self, node: Node) -> bool:
        return node.type in {"identifier", "constant"}


class RubyExtractor(StructuralExtractor):
    rules = RubyRules
