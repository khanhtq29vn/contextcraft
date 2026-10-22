"""CSS selectors, declarations, and grouping rules."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.generic import GenericExtractor
from contextcraft.models import ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class CSSExtractor(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"import_statement"})

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "rule_set": "rule",
        "media_statement": "media_query",
        "supports_statement": "supports_query",
        "keyframes_statement": "keyframes",
        "keyframe_block": "keyframe",
        "at_rule": "at_rule",
        "declaration": "property",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "declaration":
            name = self.name_node(node)
            if name is not None:
                if (name.text or b"").startswith(b"--"):
                    return "custom_property"
                if (name.text or b"").startswith(b"$"):
                    return "variable"
        return self.NODE_TYPES.get(node.type)

    def name_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type not in {"block", "keyframe_block_list", "comment"}
            ),
            None,
        )

    def body_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type in {"block", "keyframe_block_list"}
            ),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type not in {"rule_set", "keyframe_block", "at_rule"}:
            return None
        body = self.body_node(node)
        if body is None:
            return None
        # Keep grouping rules and custom properties instead of hiding their structure or values.
        if any(
            child.type not in {"declaration", "comment"}
            or self.symbol_kind(child) in {"custom_property", "variable"}
            for child in body.named_children
        ):
            return None
        return self.brace_body_range(body, source)

    def render_signature(self, symbol: SymbolNode) -> str:
        signature = " ".join(symbol.signature.split())
        if symbol.kind in {"property", "custom_property", "variable"}:
            return "/* " + signature.replace("*/", "* /") + " */"
        return f"{signature} {{ /* ... */ }}"
