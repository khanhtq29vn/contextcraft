"""JSON keys, value types, and structural type outlines."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.data import DataExtractor
from contextcraft.models import SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class JSONExtractor(DataExtractor):
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
        return (json.loads(name) or '""') if name is not None else None

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("value")

    def render_signature(self, symbol: SymbolNode) -> str:
        return json.dumps({symbol.name: symbol.kind}, ensure_ascii=False)

    def render_signatures(self, source: str, symbols: list[SymbolNode]) -> str:
        try:
            value = json.loads(source)
            return json.dumps(self._describe(value), indent=2, ensure_ascii=False) + "\n"
        except (json.JSONDecodeError, RecursionError):
            return source

    def _describe(self, value: object) -> object:
        if isinstance(value, dict):
            return {key: self._describe(item) for key, item in value.items()}
        if isinstance(value, list):
            items: list[object] = []
            seen: set[str] = set()
            for item in value:
                description = self._describe(item)
                key = json.dumps(description, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    items.append(description)
            return items
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        return "string"
