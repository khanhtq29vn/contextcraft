"""Shared contract for language-specific AST extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from contextcraft.models import ASTParseResult, ByteRange, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node


class LanguageExtractor(ABC):
    """Language rules consumed by the shared AST traversal and elider."""

    NODE_TYPES: ClassVar[dict[str, str]] = {}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset()
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = True
    PRESERVE_WHITESPACE: ClassVar[bool] = False

    def parse_fallback(self, content: str) -> ASTParseResult:
        """Leave source intact when no reliable structural analysis is available."""
        return ASTParseResult([], [], [], [])

    def should_extract(self, root: Node) -> bool:
        return self.ALLOW_SYNTAX_ERRORS or not root.has_error

    @abstractmethod
    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        """Classify a declaration in its enclosing grammar scope."""
        ...

    def unwrap_declaration(self, node: Node, source: bytes) -> tuple[Node, list[str]]:
        return node, []

    def name_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("name")

    def symbol_name(self, node: Node, source: bytes) -> str | None:
        name = self.name_node(node)
        return (
            source[name.start_byte : name.end_byte].decode("utf-8").strip()
            if name is not None
            else None
        )

    def extract_signature(self, node: Node, outer_node: Node, source: bytes) -> str:
        name = self.name_node(node)
        body = self.body_node(node)
        start = (
            min(outer_node.start_byte, name.start_byte)
            if name is not None
            else outer_node.start_byte
        )
        end = body.start_byte if body is not None else node.end_byte
        signature = source[start:end].decode("utf-8", errors="replace")
        return signature.strip().rstrip(":").rstrip("{").strip()

    def render_signatures(self, source: str, symbols: list[SymbolNode]) -> str | None:
        """Optionally render a complete document outline instead of individual declarations."""
        return None

    def body_node(self, node: Node) -> Node | None:
        return node.child_by_field_name("body")

    @abstractmethod
    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        """Select content that can be removed without hiding nested structure."""
        ...

    @abstractmethod
    def elision_marker(self, span: ByteRange) -> str:
        """Render a replacement in the language's syntax."""
        ...

    @abstractmethod
    def render_signature(self, symbol: SymbolNode) -> str:
        """Render a compact declaration summary."""
        ...

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        chunks: list[str] = []
        first: Node | None = None
        last: Node | None = None
        anchor = outer_node
        previous = anchor.prev_named_sibling

        while previous is not None:
            # Some grammars include the trailing newline in line-comment spans.
            end_line = previous.end_point[0] - (previous.end_point[1] == 0)
            gap = source[previous.end_byte : anchor.start_byte]
            if anchor.start_point[0] - end_line > 1 or gap.strip():
                break
            if self.is_doc_attribute(previous):
                anchor = previous
                previous = previous.prev_named_sibling
                continue
            if not self.is_doc_comment(previous, source):
                break

            line_start = source.rfind(b"\n", 0, previous.start_byte) + 1
            if source[line_start : previous.start_byte].strip():
                break
            chunks.append(source[previous.start_byte : previous.end_byte].decode("utf-8").strip())
            first = previous
            if last is None:
                last = previous
            anchor = previous
            previous = previous.prev_named_sibling

        if first is None or last is None:
            return None, None
        return "\n".join(reversed(chunks)), ByteRange(
            start_byte=first.start_byte,
            end_byte=last.end_byte,
            start_line=first.start_point[0] + 1,
            end_line=last.end_point[0] + (last.end_point[1] != 0),
        )

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return False

    def is_doc_attribute(self, node: Node) -> bool:
        return False

    def is_reference(self, node: Node) -> bool:
        """Recognize identifier nodes without filtering user-defined names."""
        return node.type in {"identifier", "type_identifier", "property_identifier"}

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return not name.startswith("_")

    def enclosing_scope(self, node: Node, source: bytes) -> tuple[str, str] | None:
        """Return an implicit scope supplied by an impl block or receiver."""
        return None

    @staticmethod
    def node_range(node: Node) -> ByteRange:
        return ByteRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )

    @staticmethod
    def brace_body_range(body: Node | None, source: bytes) -> ByteRange | None:
        if body is None:
            return None
        text = source[body.start_byte : body.end_byte]
        if not (text.startswith(b"{") and text.endswith(b"}") and len(text) > 2):
            return None
        return LanguageExtractor.node_range(body)
