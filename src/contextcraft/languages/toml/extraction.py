from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.rules.data import DataExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class TOMLRules(DataExtractor):
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "table": "table",
        "table_array_element": "table_array",
        "string": "string",
        "integer": "integer",
        "float": "float",
        "boolean": "boolean",
        "array": "array",
        "inline_table": "inline_table",
        "offset_date_time": "datetime",
        "local_date_time": "datetime",
        "local_date": "date",
        "local_time": "time",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type in {"table", "table_array_element"}:
            return self.NODE_TYPES[node.type]
        if node.type != "pair":
            return None
        value = self.body_node(node)
        return self.NODE_TYPES.get(value.type, "value") if value is not None else "value"

    def name_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type in {"bare_key", "quoted_key", "dotted_key"}
            ),
            None,
        )

    def body_node(self, node: Node) -> Node | None:
        if node.type in {"table", "table_array_element"}:
            return next((child for child in node.named_children if child.type == "pair"), None)
        return next(
            (
                child
                for child in node.named_children
                if child.type not in {"bare_key", "quoted_key", "dotted_key", "comment"}
            ),
            None,
        )


class TOMLExtractor(StructuralExtractor):
    rules = TOMLRules
