"""Shared extraction behavior for structured data formats."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from contextcraft.languages.base import LanguageExtractor
from contextcraft.models import ByteRange

if TYPE_CHECKING:
    from tree_sitter import Node


class DataExtractor(LanguageExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    PRESERVE_WHITESPACE: ClassVar[bool] = True

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return True

    def is_reference(self, node: Node) -> bool:
        return False

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        value = self.body_node(node)
        if value is None or value.type != "string":
            return None
        return self.node_range(value)

    def elision_marker(self, span: ByteRange) -> str:
        return '"<elided>"'
