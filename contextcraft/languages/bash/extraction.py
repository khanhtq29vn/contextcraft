from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class BashRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"function_definition": "function"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["command"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        name = node.child_by_field_name("name")
        argument = node.child_by_field_name("argument")
        if name is None or name.text not in {b"source", b"."} or argument is None:
            return []
        if argument.type not in {"word", "raw_string", "string"} or any(
            child.type in {"expansion", "simple_expansion", "command_substitution"}
            for child in argument.named_children
        ):
            return []
        return [source[argument.start_byte : argument.end_byte].decode("utf-8").strip("\"'")]

    def is_reference(self, node: Node) -> bool:
        return node.type == "variable_name" or (
            node.type == "word" and node.parent is not None and node.parent.type == "command_name"
        )


class BashExtractor(StructuralExtractor):
    rules = BashRules
