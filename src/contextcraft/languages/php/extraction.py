from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class PHPRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "trait_declaration": "trait",
        "enum_declaration": "enum",
        "function_definition": "function",
        "method_declaration": "method",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        [
            "include_expression",
            "include_once_expression",
            "namespace_use_declaration",
            "require_expression",
            "require_once_expression",
        ]
    )

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("name")

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        if node.type == "namespace_use_declaration":
            group = node.child_by_field_name("body")
            prefix = ""
            if group is not None:
                namespace = next(
                    (child for child in node.named_children if child.type == "namespace_name"), None
                )
                if namespace is not None:
                    prefix = (
                        source[namespace.start_byte : namespace.end_byte].decode("utf-8") + "\\"
                    )
            return [
                prefix
                + source[child.start_byte : child.end_byte].decode("utf-8").split(" as ")[0].strip()
                for child in (group or node).named_children
                if child.type == "namespace_use_clause"
            ]
        value = next(iter(node.named_children), None)
        if value is None or value.type not in {"string", "encapsed_string"}:
            return []
        if any(child.type != "string_content" for child in value.named_children):
            return []
        return [source[value.start_byte + 1 : value.end_byte - 1].decode("utf-8")]

    def is_reference(self, node: Node) -> bool:
        return node.type == "variable_name" or (
            node.type == "name" and node.parent is not None and node.parent.type != "variable_name"
        )

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return not any(
            child.type == "visibility_modifier" and child.text == b"private"
            for child in node.named_children
        )


class PHPExtractor(StructuralExtractor):
    rules = PHPRules
