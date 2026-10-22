from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class GraphQLRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "object_type_definition": "type",
        "interface_type_definition": "interface",
        "input_object_type_definition": "input",
        "enum_type_definition": "enum",
        "scalar_type_definition": "scalar",
        "operation_definition": "operation",
        "fragment_definition": "fragment",
        "union_type_definition": "union",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset([])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "name"), None)

    def body_node(self, node: Node) -> Node | None:
        return next(
            (
                child
                for child in node.named_children
                if child.type
                in {
                    "fields_definition",
                    "selection_set",
                    "input_fields_definition",
                    "enum_values_definition",
                }
            ),
            None,
        )

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        return None

    def is_reference(self, node: Node) -> bool:
        return node.type == "name"


class GraphQLExtractor(StructuralExtractor):
    rules = GraphQLRules
