"""Go functions, receiver methods, and named type declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.generic import GenericExtractor
from contextcraft.models import ByteRange

if TYPE_CHECKING:
    from tree_sitter import Node


class GoExtractor(GenericExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"import_declaration"})

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "function_declaration": "function",
        "method_declaration": "method",
        "method_elem": "method",
        "type_alias": "type_alias",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "type_spec":
            type_node = node.child_by_field_name("type")
            if type_node is not None:
                if type_node.type == "struct_type":
                    return "struct"
                if type_node.type == "interface_type":
                    return "interface"
            return "type_alias"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("name")

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return name[0].isupper()

    def enclosing_scope(self, node: Node, source: bytes) -> tuple[str, str] | None:
        if node.type != "method_declaration":
            return None

        receiver = node.child_by_field_name("receiver")
        if receiver is None:
            return None
        parameter = next(
            (child for child in receiver.named_children if child.type == "parameter_declaration"),
            None,
        )
        if parameter is None:
            return None

        type_node = parameter.child_by_field_name("type")
        while type_node is not None:
            if type_node.type == "pointer_type":
                type_node = next(iter(type_node.named_children), None)
            elif type_node.type == "generic_type":
                type_node = type_node.child_by_field_name("type")
            else:
                name = source[type_node.start_byte : type_node.end_byte].decode("utf-8")
                return name, "receiver"
        return None

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type not in {"method_elem", "method_declaration", "function_declaration"}:
            return None
        return self.brace_body_range(self.body_node(node), source)

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "comment" and source[node.start_byte : node.end_byte].startswith(b"//")

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        parent = outer_node.parent
        if (
            node.type in {"type_spec", "type_alias"}
            and parent is not None
            and parent.type == "type_declaration"
            and not any(child.type == "(" for child in parent.children)
        ):
            outer_node = parent
        return super().extract_docstring(node, outer_node, source)
