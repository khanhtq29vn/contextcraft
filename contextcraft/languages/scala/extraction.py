from __future__ import annotations

import re
from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class ScalaRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "class_definition": "class",
        "object_definition": "class",
        "trait_definition": "trait",
        "function_definition": "function",
        "function_declaration": "function",
        "type_definition": "type_alias",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["import_declaration"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return (
            self.node_range(body)
            if node.type == "function_definition" and body is not None
            else None
        )

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        return not re.search(
            rb"\bprivate\b", source[node.start_byte : (self.body_node(node) or node).start_byte]
        )


class ScalaExtractor(StructuralExtractor):
    rules = ScalaRules
