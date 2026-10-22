from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class RRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"function_definition": "function"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["call"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        parent = node.parent
        if (
            parent is not None
            and parent.type == "binary_operator"
            and parent.child_by_field_name("rhs") == node
        ):
            operator = parent.child_by_field_name("operator")
            name = parent.child_by_field_name("lhs")
            if (
                operator is not None
                and operator.type in {"<-", "<<-", "="}
                and name is not None
                and name.type in {"identifier", "string"}
            ):
                return name
        return None

    def unwrap_declaration(self, node: Node, source: bytes) -> tuple[Node, list[str]]:
        if node.type == "binary_operator":
            value = node.child_by_field_name("rhs")
            if (
                value is not None
                and value.type == "function_definition"
                and self.name_node(value) is not None
            ):
                return value, []
        return node, []

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return (
            self.node_range(body)
            if node.type == "function_definition" and body is not None
            else None
        )

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if (
            function is None
            or function.text not in {b"library", b"require", b"source"}
            or arguments is None
        ):
            return []
        argument = next(iter(arguments.named_children), None)
        value = argument.child_by_field_name("value") if argument is not None else None
        if value is None or value.type not in {"identifier", "string"}:
            return []
        return [source[value.start_byte : value.end_byte].decode("utf-8").strip("\"'")]


class RExtractor(StructuralExtractor):
    rules = RRules
