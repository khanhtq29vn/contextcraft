from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class SQLRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "create_table": "table",
        "create_view": "view",
        "create_function": "function",
        "create_index": "index",
        "create_schema": "schema",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset([])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        reference = next(
            (child for child in node.named_children if child.type == "object_reference"), None
        )
        return reference.child_by_field_name("name") if reference is not None else None

    def body_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type in {"column_definitions", "create_query"}
            ),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        return None


class SQLExtractor(StructuralExtractor):
    rules = SQLRules
