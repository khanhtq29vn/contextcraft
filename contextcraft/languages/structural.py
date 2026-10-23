from __future__ import annotations

import json
from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange, Import, ParsedAst, Symbol
from contextcraft.ast.scope import Binding, Reference, Scope, ScopeGraph
from contextcraft.ast.traversal import TraversalEvent, traverse
from contextcraft.languages.base import BaseExtractor, SignaturesBuilder, SkeletonBuilder
from contextcraft.languages.rules.base import LanguageExtractor
from contextcraft.languages.rules.generic import GenericExtractor


class StructuralExtractor(BaseExtractor):
    rules: ClassVar[type[LanguageExtractor]] = GenericExtractor

    def extract(self, root: Node, source: bytes) -> ParsedAst:
        rules = self.rules()
        graph = ScopeGraph(scopes=[Scope(root.start_byte, root.end_byte, kind="module")])
        parsed = ParsedAst(source=source, scope_graph=graph, has_errors=root.has_error)
        if not rules.should_extract(root):
            return parsed
        symbols: list[tuple[Node, Symbol, str]] = []
        contexts: list[tuple[Node, str, Symbol | None]] = []
        named_symbols: dict[str, Symbol] = {}
        scopes: list[tuple[Node, Scope]] = [(root, graph.scopes[0])]
        unwrapped: set[int] = set()
        bound: set[int] = set()

        def bind(node: Node, scope: Scope, name: str | None = None) -> None:
            if node.id in bound:
                return
            bound.add(node.id)
            text = (
                name
                if name is not None
                else source[node.start_byte : node.end_byte].decode("utf-8")
            )
            binding = Binding(text, node.start_byte, node.end_byte, scope)
            scope.bindings[text] = binding
            graph.bindings.append(binding)

        for event, outer in traverse(root):
            if event is TraversalEvent.LEAVE:
                if symbols and symbols[-1][0] == outer:
                    symbols.pop()
                if contexts and contexts[-1][0] == outer:
                    contexts.pop()
                if len(scopes) > 1 and scopes[-1][0] == outer:
                    scopes.pop()
                continue
            if not outer.is_named:
                continue
            scope = scopes[-1][1]
            node, _ = rules.unwrap_declaration(outer, source)
            parent_type = symbols[-1][2] if symbols else None
            parent_symbol = symbols[-1][1] if symbols else None
            context = rules.enclosing_scope(outer, source)
            if context is not None:
                context_name, context_type = context
                contexts.append((outer, context_type, named_symbols.get(context_name)))
            if contexts and (not symbols or contexts[-1][0].start_byte > symbols[-1][0].start_byte):
                _, parent_type, parent_symbol = contexts[-1]
            if context is not None and rules.symbol_kind(node, parent_type) is None:
                scope = Scope(node.start_byte, node.end_byte, parent=scope, kind=context[1])
                graph.scopes.append(scope)
                scopes.append((outer, scope))
            if node.id not in unwrapped:
                kind = rules.symbol_kind(node, parent_type)
                name_node = rules.name_node(node) if kind is not None else None
                if kind is not None:
                    name = rules.symbol_name(node, source)
                    _, doc = rules.extract_docstring(node, outer, source)
                    body = rules.body_node(node)
                    end = body.start_byte if body is not None else node.end_byte
                    end = outer.start_byte + len(source[outer.start_byte : end].rstrip())
                    symbol = Symbol(
                        name=name,
                        kind=kind,
                        declaration_range=ByteRange(outer.start_byte, outer.end_byte),
                        signature_range=ByteRange(outer.start_byte, end),
                        body_range=rules.elidable_body_range(
                            node, source, doc.end_byte if doc else None
                        ),
                        docstring_range=doc,
                        parent=parent_symbol,
                        is_public=name is not None and rules.is_exported(node, name, source),
                    )
                    parsed.symbols.append(symbol)
                    if name is not None and kind in {"class", "struct", "trait", "interface"}:
                        named_symbols[name] = symbol
                    symbols.append((outer, symbol, node.type))
                    if name is not None and name_node is not None:
                        bind(name_node, scope, name)
                    if kind in {"function", "method", "class", "struct", "trait", "module"}:
                        scope = Scope(node.start_byte, node.end_byte, parent=scope, kind=kind)
                        graph.scopes.append(scope)
                        scopes.append((outer, scope))
                    if node != outer:
                        unwrapped.add(node.id)

            if outer.type in rules.IMPORT_NODE_TYPES:
                for module in rules.import_modules(outer, source):
                    parsed.imports.append(
                        Import(module, ByteRange(outer.start_byte, outer.end_byte))
                    )

            pattern = None
            if outer.type in {"assignment", "short_var_declaration"}:
                pattern = outer.child_by_field_name("left")
            elif outer.type in {
                "variable_declarator",
                "init_declarator",
                "parameter",
                "simple_parameter",
                "variadic_parameter",
                "property_promotion_parameter",
                "let_declaration",
            }:
                pattern = (
                    outer.child_by_field_name("name")
                    or outer.child_by_field_name("pattern")
                    or outer.child_by_field_name("declarator")
                )
                if pattern is None and outer.type == "parameter":
                    pattern = next(
                        (
                            child
                            for child in outer.named_children
                            if child.type == "simple_identifier"
                        ),
                        None,
                    )
            elif outer.type in {"parameters", "lambda_parameters", "method_parameters"}:
                for child in outer.named_children:
                    if child.type == "identifier":
                        bind(child, scope)
            elif outer.type in {"typed_parameter", "default_parameter", "typed_default_parameter"}:
                pattern = outer.child_by_field_name("name") or next(
                    iter(outer.named_children), None
                )
            if pattern is not None:
                pending = [pattern]
                while pending:
                    part = pending.pop()
                    if part.type in {"identifier", "simple_identifier", "variable_name"}:
                        bind(part, scope)
                    elif part.type in {
                        "tuple_pattern",
                        "list_pattern",
                        "pattern_list",
                        "expression_list",
                        "ref_pattern",
                        "mut_pattern",
                    }:
                        pending.extend(reversed(part.named_children))

            if rules.is_reference(outer) and outer.id not in bound:
                ref = Reference(
                    source[outer.start_byte : outer.end_byte].decode("utf-8"),
                    outer.start_byte,
                    outer.end_byte,
                    scope,
                )
                graph.references.append(ref)
                scope.references.append(ref)
        return parsed

    def build_scopes(self, root: Node, source: bytes) -> ScopeGraph:
        return self.extract(root, source).scope_graph


class StructuralSkeletonBuilder(SkeletonBuilder):
    marker: ClassVar[bytes | None] = None

    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")
        replacements = sorted(
            self._replacements(parsed),
            key=lambda edit: (edit[0].start_byte, -edit[0].end_byte),
        )
        edits: list[tuple[ByteRange, bytes]] = []
        end = 0
        for span, content in replacements:
            if span.start_byte < end:
                continue
            edits.append((span, content))
            end = span.end_byte

        buffer = bytearray(parsed.source)
        for span, content in reversed(edits):
            buffer[span.start_byte : span.end_byte] = content
        return buffer.decode("utf-8")

    def _replacements(self, parsed: ParsedAst) -> list[tuple[ByteRange, bytes]]:
        if self.marker is None:
            return []
        return [
            (symbol.body_range, self.marker)
            for symbol in parsed.symbols
            if symbol.body_range is not None
        ]


class StructuralSignaturesBuilder(SignaturesBuilder):
    style: ClassVar[str] = "declarations"

    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")
        if self.style == "outline":
            if not parsed.symbols:
                return parsed.source.decode("utf-8")
            return (
                json.dumps(
                    [
                        {"name": symbol.qualified_name, "kind": symbol.kind}
                        for symbol in parsed.symbols
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
        lines = self._import_lines(parsed)
        for symbol in parsed.symbols:
            if not symbol.is_public and symbol.name not in {"__init__", "__call__", "main"}:
                continue
            parent = symbol.parent
            depth = 0
            while parent is not None and parent.kind in {
                "class",
                "struct",
                "trait",
                "module",
                "interface",
            }:
                depth += 1
                parent = parent.parent
            if parent is not None:
                continue
            signature = parsed.text(symbol.signature_range)
            if self.style == "python":
                has_children = any(
                    child.parent is symbol
                    and (child.is_public or child.name in {"__init__", "__call__", "main"})
                    for child in parsed.symbols
                )
                signature = signature.rstrip().rstrip(":") + (
                    ":" if symbol.kind == "class" and has_children else ": ..."
                )
            elif symbol.kind in {"class", "struct", "enum", "trait", "interface"}:
                signature += " { ... }"
            else:
                signature += ";"
            lines.append("    " * depth + signature)
        return "\n".join(lines) + "\n" if lines else ""


class BlockSignaturesBuilder(SignaturesBuilder):
    prefix: ClassVar[str] = ""
    opening: ClassVar[str] = " {"
    closing: ClassVar[str] = "}"
    function_suffix: ClassVar[str] = " {}"
    container_kinds: ClassVar[frozenset[str]] = frozenset(
        {"class", "struct", "trait", "interface", "module", "enum"}
    )

    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        lines = self._import_lines(parsed)
        containers: list[Symbol] = []
        for symbol in parsed.symbols:
            if symbol.name is None or not symbol.is_public:
                continue
            parent = symbol.parent
            while parent is not None and parent.is_public and parent.kind in self.container_kinds:
                parent = parent.parent
            if parent is not None:
                continue

            while containers and symbol.parent is not containers[-1]:
                containers.pop()
                lines.append("    " * len(containers) + self.closing)

            indent = "    " * len(containers)
            signature = parsed.text(symbol.signature_range).rstrip()
            if symbol.signature_range.end_byte == symbol.declaration_range.end_byte:
                lines.append(indent + signature)
            elif symbol.kind in self.container_kinds:
                lines.append(indent + signature + self.opening)
                containers.append(symbol)
            else:
                lines.append(indent + self._render_function(signature).replace("\n", "\n" + indent))

        while containers:
            containers.pop()
            lines.append("    " * len(containers) + self.closing)
        return self.prefix + "\n".join(lines) + "\n" if lines else ""

    def _render_function(self, signature: str) -> str:
        return signature + self.function_suffix
