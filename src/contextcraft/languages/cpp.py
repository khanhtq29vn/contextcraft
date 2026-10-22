"""C++ declarations using C-compatible declarator and body lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.c import CExtractor
from contextcraft.models import ByteRange

if TYPE_CHECKING:
    from tree_sitter import Node


class CppExtractor(CExtractor):
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "function_definition" and parent_type in {
            "struct_specifier",
            "class_specifier",
        }:
            return "method"
        return self.NODE_TYPES.get(node.type)

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        while outer_node.parent is not None and outer_node.parent.type == "template_declaration":
            outer_node = outer_node.parent
        return super().extract_docstring(node, outer_node, source)
