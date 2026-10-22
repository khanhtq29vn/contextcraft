"""HTML element structure, attributes, and text-content elision."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.base import LanguageExtractor
from contextcraft.models import ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class HTMLExtractor(LanguageExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset()

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "element": "element",
        "script_element": "script",
        "style_element": "style",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        kind = self.NODE_TYPES.get(node.type)
        if kind != "element":
            return kind
        name = self.name_node(node)
        tag = (name.text or b"").lower() if name is not None else b""
        if tag in {b"h1", b"h2", b"h3", b"h4", b"h5", b"h6"}:
            return "heading"
        if tag == b"title":
            return "title"
        if tag in {
            b"area",
            b"base",
            b"br",
            b"col",
            b"embed",
            b"hr",
            b"img",
            b"input",
            b"link",
            b"meta",
            b"param",
            b"source",
            b"track",
            b"wbr",
        } or any(child.type == "self_closing_tag" for child in node.named_children):
            return "void_element"
        return kind

    def name_node(self, node: Node) -> Node | None:
        opening = next(
            (
                child
                for child in node.named_children
                if child.type in {"start_tag", "self_closing_tag"}
            ),
            None,
        )
        if opening is None:
            return None
        return next((child for child in opening.named_children if child.type == "tag_name"), None)

    def body_node(self, node: Node) -> Node | None:
        if self.symbol_kind(node) in {"heading", "title"}:
            return None
        return next(
            (
                child
                for child in node.named_children
                if child.type not in {"start_tag", "self_closing_tag"}
            ),
            None,
        )

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return True

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type != "element":
            return None
        name = self.name_node(node)
        if name is None or (name.text or b"").lower() in {
            b"title",
            b"h1",
            b"h2",
            b"h3",
            b"h4",
            b"h5",
            b"h6",
        }:
            return None

        children = node.named_children
        if len(children) < 3 or children[0].type != "start_tag" or children[-1].type != "end_tag":
            return None
        # Elide leaf prose only, keeping nested elements and embedded scripts/styles intact.
        if any(child.type not in {"text", "entity"} for child in children[1:-1]):
            return None
        opening, closing = children[0], children[-1]
        return ByteRange(
            start_byte=opening.end_byte,
            end_byte=closing.start_byte,
            start_line=opening.end_point[0] + 1,
            end_line=closing.start_point[0] + 1,
        )

    def elision_marker(self, span: ByteRange) -> str:
        return f"<!-- ... elided {span.line_count} lines ... -->"

    def render_signature(self, symbol: SymbolNode) -> str:
        signature = " ".join(symbol.signature.split())
        if symbol.kind in {"void_element", "heading", "title"}:
            return signature
        return f"{signature}<!-- ... --></{symbol.name}>"
