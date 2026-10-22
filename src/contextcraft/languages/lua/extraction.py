from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class LuaRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "function_declaration": "function",
        "function_definition": "function",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["function_call"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        name = node.child_by_field_name("name")
        if name is None and node.parent is not None and node.parent.type == "expression_list":
            assignment = node.parent.parent
            if assignment is not None and assignment.type == "assignment_statement":
                variables = next(
                    (child for child in assignment.named_children if child.type == "variable_list"),
                    None,
                )
                if (
                    variables is not None
                    and len(variables.named_children) == 1
                    and len(node.parent.named_children) == 1
                ):
                    name = variables.named_children[0]
        return name

    def unwrap_declaration(self, node: Node, source: bytes) -> tuple[Node, list[str]]:
        if node.type == "variable_declaration":
            assignment = next(
                (child for child in node.named_children if child.type == "assignment_statement"),
                None,
            )
            if assignment is not None:
                return self.unwrap_declaration(assignment, source)
        if node.type == "assignment_statement":
            expressions = next(
                (child for child in node.named_children if child.type == "expression_list"), None
            )
            if expressions is not None and len(expressions.named_children) == 1:
                value = expressions.named_children[0]
                if value.type == "function_definition" and self.name_node(value) is not None:
                    return value, []
        return node, []

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return self.node_range(body) if body is not None and node.type in self.NODE_TYPES else None

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        name = node.child_by_field_name("name")
        if name is None or name.text != b"require":
            return []
        arguments = node.child_by_field_name("arguments")
        if arguments is None or len(arguments.named_children) != 1:
            return []
        argument = arguments.named_children[0]
        if argument.type != "string":
            return []
        content = argument.child_by_field_name("content")
        return (
            [source[content.start_byte : content.end_byte].decode("utf-8")]
            if content is not None
            else []
        )


class LuaExtractor(StructuralExtractor):
    rules = LuaRules
