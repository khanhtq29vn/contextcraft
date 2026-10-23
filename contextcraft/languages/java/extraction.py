from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class JavaRules(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"package_declaration", "import_declaration"}
    )
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "record_declaration": "class",
        "constructor_declaration": "constructor",
        "compact_constructor_declaration": "constructor",
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
        if self.NODE_TYPES.get(node.type) not in {"method", "constructor"}:
            return None
        return self.brace_body_range(self.body_node(node), source)

    def parameter_nodes(self, node: Node) -> list[Node]:
        parameters = node.child_by_field_name("parameters")
        if parameters is None:
            return []
        return [
            name
            for parameter in parameters.named_children
            if (name := parameter.child_by_field_name("name")) is not None
        ]

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        modifiers = next(
            (child for child in node.named_children if child.type == "modifiers"), None
        )
        return modifiers is None or all(child.type != "private" for child in modifiers.children)

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "block_comment" and source[node.start_byte : node.end_byte].startswith(
            b"/**"
        )


class JavaExtractor(StructuralExtractor):
    rules = JavaRules
