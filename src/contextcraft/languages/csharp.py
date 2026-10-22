"""C# type and method declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.generic import GenericExtractor
from contextcraft.models import ByteRange

if TYPE_CHECKING:
    from tree_sitter import Node


class CSharpExtractor(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"using_directive"})

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "struct_declaration": "struct",
        "enum_declaration": "enum",
        "method_declaration": "method",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("name")

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type != "method_declaration":
            return None
        return self.brace_body_range(self.body_node(node), source)

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "comment" and source[node.start_byte : node.end_byte].startswith(
            (b"///", b"/**")
        )
