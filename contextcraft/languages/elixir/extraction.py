from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.base import LanguageExtractor
from contextcraft.languages.structural import StructuralExtractor


class ElixirRules(LanguageExtractor):
    """Recognize definition macros without treating ordinary calls as declarations."""

    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"call"})
    _DEFINITIONS: ClassVar[frozenset[bytes]] = frozenset(
        {b"def", b"defp", b"defmacro", b"defmacrop"}
    )

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        target = node.child_by_field_name("target") if node.type == "call" else None
        if target is None:
            return None
        if target.text in {b"defmodule", b"defprotocol"}:
            return "module"
        return "function" if target.text in self._DEFINITIONS else None

    @staticmethod
    def _head(node: Node) -> Node | None:
        arguments = next(
            (child for child in node.named_children if child.type == "arguments"), None
        )
        head = next(iter(arguments.named_children), None) if arguments is not None else None
        if head is not None and head.type == "binary_operator":
            head = head.child_by_field_name("left")
        return head

    def name_node(self, node: Node) -> Node | None:
        head = self._head(node)
        if head is not None and head.type == "call":
            return head.child_by_field_name("target")
        return head

    def body_node(self, node: Node) -> Node | None:
        block = next((child for child in node.named_children if child.type == "do_block"), None)
        if block is not None:
            return block
        arguments = next(
            (child for child in node.named_children if child.type == "arguments"), None
        )
        if arguments is not None:
            for child in arguments.named_children:
                if child.type == "keywords":
                    for pair in child.named_children:
                        key = pair.child_by_field_name("key")
                        if key is not None and (key.text or b"").strip() == b"do:":
                            return pair.child_by_field_name("value")
        return None

    def signature_range(self, node: Node, outer_node: Node, source: bytes) -> ByteRange:
        signature = super().signature_range(node, outer_node, source)
        if self.symbol_kind(node) == "module":
            header = source[signature.start_byte : signature.end_byte]
            if header.rstrip().endswith(b"do:"):
                end = header.rfind(b",")
                if end >= 0:
                    return ByteRange(
                        signature.start_byte, signature.start_byte + len(header[:end].rstrip())
                    )
        return signature

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        target = node.child_by_field_name("target")
        body = self.body_node(node)
        if target is not None and target.text in self._DEFINITIONS and body is not None:
            return self.node_range(body)
        return None

    def parameter_nodes(self, node: Node) -> list[Node]:
        if self.symbol_kind(node) != "function":
            return []
        head = self._head(node)
        if head is None:
            return []
        arguments = next(
            (child for child in head.named_children if child.type == "arguments"), None
        )
        pending = list(arguments.named_children) if arguments is not None else []
        parameters = []
        while pending:
            pattern = pending.pop()
            if pattern.type == "identifier":
                parameters.append(pattern)
            elif pattern.type == "binary_operator":
                left = pattern.child_by_field_name("left")
                if left is not None:
                    pending.append(left)
                operator = pattern.child_by_field_name("operator")
                if operator is not None and operator.text not in {b"\\\\", b"::"}:
                    right = pattern.child_by_field_name("right")
                    if right is not None:
                        pending.append(right)
            elif pattern.type in {"tuple", "list", "map", "map_content", "keywords", "pair"}:
                pending.extend(pattern.named_children)
        return parameters

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        target = node.child_by_field_name("target")
        if target is None or target.text not in {b"alias", b"import", b"require", b"use"}:
            return []
        head = self._head(node)
        if head is not None and head.type == "alias":
            return [source[head.start_byte : head.end_byte].decode("utf-8")]
        if head is not None and head.type == "dot":
            prefix = head.child_by_field_name("left")
            names = head.child_by_field_name("right")
            if (
                prefix is not None
                and prefix.type == "alias"
                and names is not None
                and names.type == "tuple"
            ):
                return [
                    f"{(prefix.text or b'').decode()}.{(name.text or b'').decode()}"
                    for name in names.named_children
                    if name.type == "alias"
                ]
        return []

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        target = node.child_by_field_name("target")
        return target is not None and target.text not in {b"defp", b"defmacrop"}

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type == "unary_operator" and (node.text or b"").startswith(
            (b"@doc ", b"@moduledoc ")
        )


class ElixirExtractor(StructuralExtractor):
    rules = ElixirRules
