from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING, ClassVar

from contextcraft.ast import ByteRange, EmbeddedRegion, ParsedAst
from contextcraft.ast.parser import parse
from contextcraft.ast.traversal import TraversalEvent, traverse
from contextcraft.languages.base import Language
from contextcraft.languages.css.language import CSSLanguage
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.rules.base import LanguageExtractor
from contextcraft.languages.structural import StructuralExtractor

if TYPE_CHECKING:
    from tree_sitter import Node


class HTMLRules(LanguageExtractor):
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
        if any(child.type not in {"text", "entity"} for child in children[1:-1]):
            return None
        opening, closing = (children[0], children[-1])
        return ByteRange(start_byte=opening.end_byte, end_byte=closing.start_byte)

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return True


class HTMLExtractor(StructuralExtractor):
    rules = HTMLRules
    _JAVASCRIPT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "",
            "module",
            "text/javascript",
            "application/javascript",
            "text/ecmascript",
            "application/ecmascript",
            "application/x-javascript",
        }
    )

    def extract(self, root: Node, source: bytes) -> ParsedAst:
        parsed = super().extract(root, source)
        if parsed.has_errors:
            return parsed

        for event, node in traverse(root):
            if event is TraversalEvent.LEAVE or node.type not in {
                "script_element",
                "style_element",
            }:
                continue
            language = self._embedded_language(node, source)
            content = next(
                (child for child in node.named_children if child.type == "raw_text"), None
            )
            if language is None or content is None or content.start_byte == content.end_byte:
                continue
            span = ByteRange(content.start_byte, content.end_byte)
            parsed.embedded_regions.append(
                EmbeddedRegion(
                    span, language, parse(source[span.start_byte : span.end_byte], language)
                )
            )
        return parsed

    @classmethod
    def _embedded_language(cls, node: Node, source: bytes) -> type[Language] | None:
        opening = next((child for child in node.named_children if child.type == "start_tag"), None)
        if opening is None:
            return None
        attributes: dict[str, str] = {}
        for attribute in opening.named_children:
            if attribute.type != "attribute":
                continue
            name = next(
                (child for child in attribute.named_children if child.type == "attribute_name"),
                None,
            )
            if name is None:
                continue
            value = next(
                (
                    child
                    for child in attribute.named_children
                    if child.type in {"attribute_value", "quoted_attribute_value"}
                ),
                None,
            )
            text = (
                source[value.start_byte : value.end_byte].decode("utf-8")
                if value is not None
                else ""
            )
            if value is not None and value.type == "quoted_attribute_value":
                text = text[1:-1]
            attributes.setdefault(
                source[name.start_byte : name.end_byte].decode("utf-8").lower(),
                unescape(text).strip().lower(),
            )

        content_type = attributes.get("type", "").split(";", 1)[0].strip()
        if node.type == "script_element":
            if "src" in attributes or content_type not in cls._JAVASCRIPT_TYPES:
                return None
            if attributes.get("lang", "javascript") not in {"js", "javascript"}:
                return None
            if not attributes.get("type") and attributes.get("language", "javascript") not in {
                "javascript",
                "js",
            }:
                return None
            return JavaScriptLanguage
        if content_type not in {"", "text/css"} or attributes.get("lang", "css") != "css":
            return None
        return CSSLanguage
