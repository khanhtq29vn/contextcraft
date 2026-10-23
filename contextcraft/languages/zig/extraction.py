from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.base import LanguageExtractor
from contextcraft.languages.structural import StructuralExtractor


class ZigRules(LanguageExtractor):
    """Extract native declarations, including sibling pub tokens and type containers."""

    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset({"VarDecl"})

    @staticmethod
    def _container(node: Node) -> Node | None:
        variable = next((child for child in node.named_children if child.type == "VarDecl"), None)
        expression = (
            next(
                (child for child in variable.named_children if child.type == "ErrorUnionExpr"), None
            )
            if variable is not None
            else None
        )
        while expression is not None:
            if expression.type == "ContainerDecl":
                return expression
            children = expression.named_children
            expression = children[0] if len(children) == 1 else None
        return None

    def symbol_kind(self, node: Node, parent_type: str | None = None) -> str | None:
        if node.type == "ContainerField":
            return "field"
        if node.type != "Decl":
            return None
        if any(child.type == "FnProto" for child in node.named_children):
            return "method" if parent_type == "Decl" else "function"
        container = self._container(node)
        if container is not None:
            kind = next(
                (child for child in container.named_children if child.type == "ContainerDeclType"),
                None,
            )
            return (
                "enum" if kind is not None and (kind.text or b"").startswith(b"enum") else "struct"
            )
        variable = next((child for child in node.named_children if child.type == "VarDecl"), None)
        if variable is not None:
            return "constant" if variable.children[0].type == "const" else "variable"
        return None

    def name_node(self, node: Node) -> Node | None:
        if node.type == "ContainerField":
            name = node.child_by_field_name("field_member")
            if name is None:
                name = next(iter(node.named_children), None)
                while name is not None and len(name.named_children) == 1:
                    name = name.named_children[0]
            return name if name is not None and name.type == "IDENTIFIER" else None
        for child in node.named_children:
            if child.type == "FnProto":
                return child.child_by_field_name("function")
            if child.type == "VarDecl":
                return child.child_by_field_name("variable_type_function")
        return None

    def body_node(self, node: Node) -> Node | None:
        return next(
            (child for child in node.named_children if child.type == "Block"), None
        ) or self._container(node)

    def declaration_range(self, node: Node, outer_node: Node, source: bytes) -> ByteRange:
        previous = outer_node.prev_sibling
        start = (
            previous.start_byte
            if previous is not None and previous.type == "pub"
            else outer_node.start_byte
        )
        following = outer_node.next_sibling
        end = (
            following.end_byte
            if node.type == "ContainerField" and following is not None and following.type == ","
            else outer_node.end_byte
        )
        return ByteRange(start, end)

    def signature_range(self, node: Node, outer_node: Node, source: bytes) -> ByteRange:
        declaration = self.declaration_range(node, outer_node, source)
        container = self._container(node)
        if container is not None:
            opening = next(child for child in container.children if child.type == "{")
            return ByteRange(
                declaration.start_byte,
                declaration.start_byte
                + len(source[declaration.start_byte : opening.start_byte].rstrip()),
            )
        if node.type == "ContainerField":
            return declaration
        return super().signature_range(node, outer_node, source)

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = next((child for child in node.named_children if child.type == "Block"), None)
        return self.node_range(body) if body is not None else None

    def parameter_nodes(self, node: Node) -> list[Node]:
        prototype = next((child for child in node.named_children if child.type == "FnProto"), None)
        parameters = (
            next(
                (child for child in prototype.named_children if child.type == "ParamDeclList"), None
            )
            if prototype is not None
            else None
        )
        return (
            [
                name
                for parameter in parameters.named_children
                if (name := parameter.child_by_field_name("parameter")) is not None
            ]
            if parameters is not None
            else []
        )

    def import_modules(self, node: Node, source: bytes) -> list[str]:
        expression = next(
            (child for child in node.named_children if child.type == "ErrorUnionExpr"), None
        )
        if expression is None or len(expression.named_children) != 1:
            return []
        call = expression.named_children[0]
        if call.type != "SuffixExpr" or len(call.named_children) != 2:
            return []
        target, arguments = call.named_children
        if target.type != "BUILTINIDENTIFIER" or target.text != b"@import":
            return []
        literal = arguments
        while literal.type != "STRINGLITERALSINGLE" and len(literal.named_children) == 1:
            literal = literal.named_children[0]
        text = literal.text or b""
        if literal.type == "STRINGLITERALSINGLE" and b"\\" not in text:
            return [text[1:-1].decode("utf-8")]
        return []

    def is_exported(self, node: Node, name: str, source: bytes) -> bool:
        previous = node.prev_sibling
        return (
            node.type == "ContainerField"
            or (previous is not None and previous.type == "pub")
            or any(child.type == "export" for child in node.children)
        )

    def is_reference(self, node: Node) -> bool:
        return node.type == "IDENTIFIER"

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"doc_comment", "container_doc_comment"}

    def extract_docstring(
        self, node: Node, outer_node: Node, source: bytes
    ) -> tuple[str | None, ByteRange | None]:
        previous = outer_node.prev_sibling
        if previous is not None and previous.type == "pub":
            outer_node = previous
        return super().extract_docstring(node, outer_node, source)


class ZigExtractor(StructuralExtractor):
    rules = ZigRules
