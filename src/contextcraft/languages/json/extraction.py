from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.rules.data import DataExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class JSONRules(DataExtractor):
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "object": "object",
        "array": "array",
        "string": "string",
        "number": "number",
        "true": "boolean",
        "false": "boolean",
        "null": "null",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type != "pair":
            return None
        value = self.body_node(node)
        return self.NODE_TYPES.get(value.type) if value is not None else None

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("key")

    def symbol_name(self, node: Node, source: bytes) -> str | None:
        name = super().symbol_name(node, source)
        return json.loads(name) or '""' if name is not None else None

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("value")


class JSONExtractor(StructuralExtractor):
    rules = JSONRules
