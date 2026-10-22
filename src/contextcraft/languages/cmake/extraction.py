from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class CMakeRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {"function_def": "function", "macro_def": "function"}
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(["normal_command"])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        command = next(
            (
                child
                for child in node.named_children
                if child.type in {"function_command", "macro_command"}
            ),
            None,
        )
        if command is None:
            return None
        arguments = next(
            (child for child in command.named_children if child.type == "argument_list"), None
        )
        return next(iter(arguments.named_children), None) if arguments is not None else None

    def body_node(self, node: Node) -> Node | None:
        return next((child for child in node.named_children if child.type == "body"), None)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return self.node_range(body) if body is not None else None

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        name = next((child for child in node.named_children if child.type == "identifier"), None)
        arguments = next(
            (child for child in node.named_children if child.type == "argument_list"), None
        )
        if (
            name is None
            or (name.text or b"").lower() not in {b"include", b"add_subdirectory", b"find_package"}
            or arguments is None
        ):
            return []
        first = next(iter(arguments.named_children), None)
        return (
            [source[first.start_byte : first.end_byte].decode("utf-8").strip('"')]
            if first is not None
            else []
        )


class CMakeExtractor(StructuralExtractor):
    rules = CMakeRules
