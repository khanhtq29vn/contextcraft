"""Rust declarations and explicit visibility."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.generic import GenericExtractor
from contextcraft.models import ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class RustExtractor(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"use_declaration", "extern_crate_declaration"}
    )

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "function_item": "function",
        "function_signature_item": "function",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "type_item": "type_alias",
        "mod_item": "module",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type in {"function_signature_item", "function_item"} and parent_type in {
            "trait_item",
            "impl_item",
        }:
            return "method"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("name")

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return any(child.type == "visibility_modifier" for child in node.children)

    def enclosing_scope(self, node: Node, source: bytes) -> tuple[str, str] | None:
        if node.type != "impl_item":
            return None

        type_node = node.child_by_field_name("type")
        if type_node is None:
            return None
        if type_node.type == "generic_type":
            type_node = type_node.child_by_field_name("type")
        if type_node is None:
            return None

        name = source[type_node.start_byte : type_node.end_byte].decode("utf-8")
        return name, "impl_item"

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type not in {"function_signature_item", "function_item"}:
            return None
        return self.brace_body_range(self.body_node(node), source)

    def render_signature(self, symbol: SymbolNode) -> str:
        signature = " ".join(symbol.signature.split())
        if symbol.kind in {"enum", "struct", "trait"}:
            return f"{signature} {{ ... }}"
        return f"{signature};"

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        if node.type not in {"line_comment", "block_comment"}:
            return False
        text = source[node.start_byte : node.end_byte]
        return (text.startswith(b"///") and not text.startswith(b"////")) or (
            text.startswith(b"/**") and not text.startswith((b"/***", b"/**/"))
        )

    def is_doc_attribute(self, node: Node) -> bool:
        return node.type == "attribute_item"
