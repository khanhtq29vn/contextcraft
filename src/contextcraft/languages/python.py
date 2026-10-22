"""Python declarations, including decorated definitions handled by traversal."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.base import LanguageExtractor
from contextcraft.models import ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class PythonExtractor(LanguageExtractor):
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"import_statement", "import_from_statement"}
    )

    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_definition": "class",
        "function_definition": "function",
    }

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "function_definition" and parent_type == "class_definition":
            return "method"
        return self.NODE_TYPES.get(node.type)

    def unwrap_declaration(self, node: Node, source: bytes) -> tuple[Node, list[str]]:
        if node.type != "decorated_definition":
            return node, []
        definition = node.child_by_field_name("definition")
        if definition is None or self.symbol_kind(definition) is None:
            return node, []
        decorators = [
            source[child.start_byte : child.end_byte].decode("utf-8").strip()
            for child in node.children
            if child.type == "decorator"
        ]
        return definition, decorators

    def extract_signature(self, node: Node, outer_node: Node, source: bytes) -> str:
        return super().extract_signature(node, node, source)

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        body = self.body_node(node)
        if body is None:
            return None, None
        statement = next((child for child in body.named_children if child.type != "comment"), None)
        if statement is None:
            return None, None

        text = source[statement.start_byte : statement.end_byte].decode("utf-8").strip()
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None, None
        if not isinstance(value, str):
            return None, None
        return text, self.node_range(statement)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        if node.type != "function_definition":
            return None
        body = self.body_node(node)
        if body is None:
            return None

        for child in body.children:
            if child.type in {"comment", "newline", "indent", ":"}:
                continue
            if doc_end_byte is not None and child.end_byte <= doc_end_byte:
                continue
            if body.end_byte > child.start_byte:
                return ByteRange(
                    start_byte=child.start_byte,
                    end_byte=body.end_byte,
                    start_line=child.start_point[0] + 1,
                    end_line=body.end_point[0] + 1,
                )
        return None

    def render_signature(self, symbol: SymbolNode) -> str:
        signature = " ".join(symbol.signature.split())
        return f"{signature}:" if symbol.kind == "class" else f"{signature}: ..."

    def elision_marker(self, span: ByteRange) -> str:
        return f"...  # [elided {span.line_count} lines]"
