from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class CRules(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"preproc_include"})
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "function_definition": "function",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "function_definition" and parent_type == "struct_specifier":
            return "method"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        name = node.child_by_field_name("name")
        if name is not None:
            return name
        declarator = node.child_by_field_name("declarator")
        while declarator is not None:
            inner = declarator.child_by_field_name("declarator")
            if inner is None:
                return declarator
            declarator = inner
        return None

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type != "function_definition":
            return None
        return self.brace_body_range(self.body_node(node), source)

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "comment" and source[node.start_byte : node.end_byte].startswith(
            (b"///", b"//!", b"/**", b"/*!")
        )


class CExtractor(StructuralExtractor):
    rules = CRules
