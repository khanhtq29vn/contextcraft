from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange, Import, ParsedAst, Symbol
from contextcraft.ast.scope import Binding, Reference, Scope, ScopeGraph
from contextcraft.ast.traversal import TraversalEvent, traverse
from contextcraft.languages.base import BaseExtractor


class JavaScriptExtractor(BaseExtractor):
    _FUNCTION_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
            "generator_function",
            "arrow_function",
            "method_definition",
        }
    )
    _DECLARATION_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "function_declaration",
            "generator_function_declaration",
            "class_declaration",
        }
    )

    def extract(self, root: Node, source: bytes) -> ParsedAst:
        parsed = super().extract(root, source)
        parents: list[tuple[Node, Symbol]] = []

        for event, node in traverse(root):
            if event is TraversalEvent.LEAVE:
                if parents and parents[-1][0] == node:
                    parents.pop()
                continue
            if not node.is_named:
                continue

            if node.type == "import_statement" or (
                node.type == "export_statement" and node.child_by_field_name("source") is not None
            ):
                module = node.child_by_field_name("source")
                if module is not None:
                    parsed.imports.append(
                        Import(
                            module=source[module.start_byte + 1 : module.end_byte - 1].decode(
                                "utf-8"
                            ),
                            declaration_range=self._range(node),
                        )
                    )

            if node.type not in self._FUNCTION_TYPES | {"class", "class_declaration"}:
                continue
            name_node = node.child_by_field_name("name")
            if node.parent is not None:
                assigned_name = None
                if node.parent.type == "variable_declarator":
                    assigned_name = node.parent.child_by_field_name("name")
                elif node.parent.type == "pair":
                    assigned_name = node.parent.child_by_field_name("key")
                if assigned_name is not None and assigned_name.type in {
                    "identifier",
                    "property_identifier",
                }:
                    name_node = assigned_name
            name = None
            if name_node is not None and name_node.type in {
                "identifier",
                "property_identifier",
                "private_property_identifier",
            }:
                name = source[name_node.start_byte : name_node.end_byte].decode("utf-8")

            body = node.child_by_field_name("body")
            signature_end = body.start_byte if body is not None else node.end_byte
            while (
                signature_end > node.start_byte
                and source[signature_end - 1 : signature_end].isspace()
            ):
                signature_end -= 1
            kind = "class" if node.type in {"class", "class_declaration"} else "function"
            if node.type == "method_definition":
                kind = "method"

            anchor = node
            while anchor.parent is not None and anchor.parent.type in {
                "export_statement",
                "lexical_declaration",
                "variable_declaration",
                "variable_declarator",
                "pair",
            }:
                anchor = anchor.parent
            previous = anchor.prev_named_sibling
            docstring_range = None
            if previous is not None and previous.type == "comment":
                comment = source[previous.start_byte : previous.end_byte]
                if (
                    comment.startswith(b"/**")
                    and anchor.start_point[0] - previous.end_point[0] <= 1
                ):
                    docstring_range = self._range(previous)

            symbol = Symbol(
                name=name,
                kind=kind,
                declaration_range=self._range(node),
                signature_range=ByteRange(node.start_byte, signature_end),
                body_range=self._range(body) if body is not None else None,
                docstring_range=docstring_range,
                parent=parents[-1][1] if parents else None,
                is_public=name is not None and not name.startswith(("_", "#")),
            )
            parsed.symbols.append(symbol)
            parents.append((node, symbol))

        return parsed

    def build_scopes(self, root: Node, source: bytes) -> ScopeGraph:
        graph = ScopeGraph()
        stack: list[tuple[Node, Scope]] = []
        binding_nodes: set[int] = set()
        ignored_nodes: set[int] = set()

        def bind(pattern: Node | None, scope: Scope) -> None:
            if pattern is None:
                return
            for identifier in self._pattern_identifiers(pattern):
                binding_nodes.add(identifier.id)
                name = source[identifier.start_byte : identifier.end_byte].decode("utf-8")
                binding = Binding(name, identifier.start_byte, identifier.end_byte, scope)
                scope.bindings[name] = binding
                graph.bindings.append(binding)

        def var_scope(scope: Scope) -> Scope:
            while scope.parent is not None and scope.kind not in {
                "function",
                "module",
                "static_block",
            }:
                scope = scope.parent
            return scope

        for event, node in traverse(root):
            if event is TraversalEvent.LEAVE:
                if stack and stack[-1][0] == node:
                    stack.pop()
                continue
            if not node.is_named:
                continue

            parent_scope = stack[-1][1] if stack else None
            if stack and stack[-1][0].type == "method_definition":
                method_name = stack[-1][0].child_by_field_name("name")
                if (
                    method_name is not None
                    and method_name.start_byte <= node.start_byte
                    and node.end_byte <= method_name.end_byte
                    and parent_scope is not None
                ):
                    # Computed method names execute outside the method's function scope.
                    parent_scope = parent_scope.parent
            if node.type in self._DECLARATION_TYPES and parent_scope is not None:
                bind(node.child_by_field_name("name"), parent_scope)

            kind = None
            if node == root:
                kind = "module"
            elif node.type in self._FUNCTION_TYPES:
                kind = "function"
            elif node.type in {"class", "class_declaration"}:
                kind = "class"
            elif node.type == "catch_clause":
                kind = "catch"
            elif node.type in {"for_statement", "for_in_statement"}:
                kind = "loop"
            elif node.type == "class_static_block":
                kind = "static_block"
            elif node.type == "switch_body" or (
                node.type == "statement_block"
                and (
                    node.parent is None
                    or node.parent.type
                    not in self._FUNCTION_TYPES | {"catch_clause", "class_static_block"}
                    or node != node.parent.child_by_field_name("body")
                )
            ):
                kind = "block"

            if kind is not None:
                scope = Scope(node.start_byte, node.end_byte, parent=parent_scope, kind=kind)
                graph.scopes.append(scope)
                stack.append((node, scope))
            else:
                assert parent_scope is not None
                scope = parent_scope

            if node.type in self._FUNCTION_TYPES:
                if node.type in {"function_expression", "generator_function"}:
                    bind(node.child_by_field_name("name"), scope)
                bind(node.child_by_field_name("parameters"), scope)
                bind(node.child_by_field_name("parameter"), scope)
            elif node.type in {"class", "class_declaration"}:
                bind(node.child_by_field_name("name"), scope)
            elif node.type == "catch_clause":
                bind(node.child_by_field_name("parameter"), scope)
            elif node.type == "variable_declarator":
                target = scope
                if node.parent is not None and node.parent.type == "variable_declaration":
                    target = var_scope(scope)
                bind(node.child_by_field_name("name"), target)
            elif node.type == "for_in_statement":
                declaration_kind = node.child_by_field_name("kind")
                if declaration_kind is not None:
                    target = var_scope(scope) if declaration_kind.type == "var" else scope
                    bind(node.child_by_field_name("left"), target)
            elif node.type == "import_statement":
                for import_event, child in traverse(node):
                    if import_event is TraversalEvent.LEAVE:
                        continue
                    if child.type == "identifier":
                        ignored_nodes.add(child.id)
                        if child.parent is not None and child.parent.type in {
                            "import_clause",
                            "namespace_import",
                        }:
                            bind(child, scope)
                    elif child.type == "import_specifier":
                        bind(
                            child.child_by_field_name("alias") or child.child_by_field_name("name"),
                            scope,
                        )

            if node.id in binding_nodes or node.id in ignored_nodes or not self._is_reference(node):
                continue
            name = source[node.start_byte : node.end_byte].decode("utf-8")
            reference = Reference(name, node.start_byte, node.end_byte, scope)
            scope.references.append(reference)
            graph.references.append(reference)

        return graph

    @staticmethod
    def _pattern_identifiers(pattern: Node) -> list[Node]:
        identifiers: list[Node] = []
        pending = [pattern]
        while pending:
            node = pending.pop()
            if node.type in {"identifier", "shorthand_property_identifier_pattern"}:
                identifiers.append(node)
            elif node.type in {"assignment_pattern", "object_assignment_pattern"}:
                left = node.child_by_field_name("left")
                if left is not None:
                    pending.append(left)
            elif node.type == "pair_pattern":
                value = node.child_by_field_name("value")
                if value is not None:
                    pending.append(value)
            elif node.type in {
                "formal_parameters",
                "object_pattern",
                "array_pattern",
                "rest_pattern",
            }:
                pending.extend(reversed(node.named_children))
        return identifiers

    @staticmethod
    def _is_reference(node: Node) -> bool:
        if node.type not in {
            "identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
        }:
            return False
        parent = node.parent
        if parent is None:
            return False
        if parent.type == "export_specifier":
            statement = parent.parent.parent if parent.parent is not None else None
            return (
                node == parent.child_by_field_name("name")
                and statement is not None
                and statement.child_by_field_name("source") is None
            )
        if parent.type in {"jsx_opening_element", "jsx_self_closing_element"}:
            return bool(node.text and node.text[:1].isupper())
        ancestor = parent
        while ancestor.type == "member_expression" and ancestor.parent is not None:
            ancestor = ancestor.parent
        return ancestor.type != "jsx_closing_element"

    @staticmethod
    def _range(node: Node) -> ByteRange:
        return ByteRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
        )
