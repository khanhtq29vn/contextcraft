"""Conservative declaration rules for grammars without a dedicated extractor."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.base import LanguageExtractor
from contextcraft.models import ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class GenericExtractor(LanguageExtractor):
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_definition": "class",
        "class_declaration": "class",
        "class_specifier": "class",
        "function_definition": "function",
        "function_declaration": "function",
        "function_item": "function",
        "arrow_function": "function",
        "method_definition": "method",
        "method_declaration": "method",
        "interface_declaration": "interface",
        "type_alias_declaration": "type_alias",
        "type_item": "type_alias",
        "struct_specifier": "struct",
        "struct_item": "struct",
        "struct_declaration": "struct",
        "enum_declaration": "enum",
        "enum_specifier": "enum",
        "enum_item": "enum",
    }

    BODY_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "block",
            "statement_block",
            "declaration_list",
            "class_body",
            "interface_body",
            "enum_body",
            "field_declaration_list",
            "compound_statement",
        }
    )

    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "import_statement",
            "import_from_statement",
            "import_declaration",
            "use_declaration",
            "preproc_include",
            "package_clause",
        }
    )

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type in {
            "arrow_function",
            "function_item",
            "function_definition",
            "function_declaration",
        } and parent_type in {
            "class_definition",
            "interface_declaration",
            "class_declaration",
            "struct_item",
            "struct_declaration",
            "struct_specifier",
            "class_specifier",
        }:
            return "method"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        name = node.child_by_field_name("name")
        if name is not None:
            return name
        return next(
            (
                child
                for child in node.children
                if child.type
                in {"identifier", "type_identifier", "field_identifier", "property_identifier"}
            ),
            None,
        )

    def body_node(self, node: Node) -> Node | None:
        body = node.child_by_field_name("body")
        if body is not None:
            return body
        return next((child for child in node.children if child.type in self.BODY_NODE_TYPES), None)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type not in {
            "method_definition",
            "method_declaration",
            "function_definition",
            "function_item",
            "arrow_function",
            "function_declaration",
        }:
            return None
        return self.brace_body_range(self.body_node(node), source)

    def render_signature(self, symbol: SymbolNode) -> str:
        signature = " ".join(symbol.signature.split())
        if symbol.kind in {"enum", "struct", "class", "interface"}:
            return f"{signature} {{ ... }}"
        return f"{signature};"

    def elision_marker(self, span: ByteRange) -> str:
        return f"{{ /* ... elided {span.line_count} lines ... */ }}"
