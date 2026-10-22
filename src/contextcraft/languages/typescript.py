"""Shared declaration extraction for JavaScript, TypeScript, and TSX grammars."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.generic import GenericExtractor
from contextcraft.models import ByteRange

if TYPE_CHECKING:
    from tree_sitter import Node


class TypeScriptExtractor(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"import_statement"})

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "abstract_class_declaration": "class",
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "function_expression": "function",
        "generator_function": "function",
        "arrow_function": "function",
        "method_definition": "method",
        "method_signature": "method",
        "abstract_method_signature": "method",
        "function_signature": "function",
        "interface_declaration": "interface",
        "type_alias_declaration": "type_alias",
        "enum_declaration": "enum",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type in {
            "generator_function",
            "arrow_function",
            "function_signature",
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
        } and parent_type in {
            "interface_declaration",
            "abstract_class_declaration",
            "class_declaration",
        }:
            return "method"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        name = node.child_by_field_name("name")
        if name is not None:
            return name

        parent = node.parent
        if parent is not None and parent.type in {
            "variable_declarator",
            "public_field_definition",
            "pair",
        }:
            return parent.child_by_field_name("name") or parent.child_by_field_name("key")
        return None

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        if name.startswith(("_", "#")):
            return False
        return not any(
            child.type == "accessibility_modifier"
            and source[child.start_byte : child.end_byte] in {b"private", b"protected"}
            for child in node.children
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type not in {
            "method_definition",
            "generator_function",
            "abstract_method_signature",
            "arrow_function",
            "method_signature",
            "function_signature",
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
        }:
            return None
        return self.brace_body_range(self.body_node(node), source)

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "comment" and source[node.start_byte : node.end_byte].startswith(b"/**")

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        anchor = outer_node
        while anchor.parent is not None and anchor.parent.type in {
            "export_statement",
            "ambient_declaration",
            "lexical_declaration",
            "variable_declaration",
            "variable_declarator",
            "public_field_definition",
            "pair",
        }:
            anchor = anchor.parent
        return super().extract_docstring(node, anchor, source)
