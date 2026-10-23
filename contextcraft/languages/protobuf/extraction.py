from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class ProtobufRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "message": "message",
        "enum": "enum",
        "service": "service",
        "rpc": "method",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["import"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        name = next(
            (
                child
                for child in node.named_children
                if child.type in {"message_name", "enum_name", "service_name", "rpc_name"}
            ),
            None,
        )
        return next(iter(name.named_children), None) if name is not None else None

    def body_node(self, node: Node) -> Node | None:
        return next(
            (child for child in node.named_children if child.type in {"message_body", "enum_body"}),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        return None


class ProtobufExtractor(StructuralExtractor):
    rules = ProtobufRules
