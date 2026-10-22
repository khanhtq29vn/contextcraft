from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.data import DataExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class YAMLRules(DataExtractor):
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "block_mapping": "mapping",
        "flow_mapping": "mapping",
        "block_sequence": "sequence",
        "flow_sequence": "sequence",
        "string_scalar": "string",
        "double_quote_scalar": "string",
        "single_quote_scalar": "string",
        "block_scalar": "string",
        "integer_scalar": "integer",
        "float_scalar": "float",
        "boolean_scalar": "boolean",
        "null_scalar": "null",
        "alias": "alias",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type not in {"block_mapping_pair", "flow_pair"}:
            return None
        value = self.body_node(node)
        return self.NODE_TYPES.get(value.type, "value") if value is not None else "null"

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("key")

    def body_node(self, node: Node) -> Node | None:
        value = node.child_by_field_name("value")
        while value is not None and value.type in {"block_node", "flow_node", "plain_scalar"}:
            value = next(
                (
                    child
                    for child in value.named_children
                    if child.type not in {"anchor", "tag", "comment"}
                ),
                None,
            )
        return value

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        wrapped = node.child_by_field_name("value")
        if wrapped is not None and any(child.type == "tag" for child in wrapped.named_children):
            return None
        value = self.body_node(node)
        if value is None or self.NODE_TYPES.get(value.type) != "string":
            return None
        return self.node_range(value)


class YAMLExtractor(StructuralExtractor):
    rules = YAMLRules
