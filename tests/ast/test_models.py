from __future__ import annotations

from dataclasses import fields

from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.ast.parser import parse
from contextcraft.ast.scope import Binding, Reference, Scope
from contextcraft.languages.html.language import HTMLLanguage


def test_embedded_region_collections_are_independent() -> None:
    parsed = parse(b"<script>run();</script>", HTMLLanguage)
    assert parsed.embedded_regions
    assert ParsedAst(source=b"").embedded_regions == []


def test_identifier_lists_are_derived_not_stored() -> None:
    parsed = ParsedAst(source=b"local external")
    scope = Scope(0, len(parsed.source))
    parsed.scope_graph.scopes.append(scope)
    binding = Binding("local", 0, 5, scope)
    reference = Reference("external", 6, 14, scope)

    assert parsed.defined_identifiers == []
    assert parsed.referenced_identifiers == []

    parsed.scope_graph.bindings.extend([binding, binding])
    parsed.scope_graph.references.extend([reference, reference])

    assert parsed.defined_identifiers == ["local"]
    assert parsed.referenced_identifiers == ["external"]
    stored_fields = {item.name for item in fields(parsed)}
    assert "defined_identifiers" not in stored_fields
    assert "referenced_identifiers" not in stored_fields


def test_symbol_qualified_names_follow_direct_parent_links() -> None:
    span = ByteRange(0, 0)
    parent = Symbol("Client", "class", span, span)
    child = Symbol("fetch", "method", span, span, parent=parent)
    parsed = ParsedAst(source=b"", symbols=[parent, child])

    assert child.parent is parent
    assert child.qualified_name == "Client.fetch"
    assert parsed.defined_identifiers == ["Client", "fetch", "Client.fetch"]


def test_parsed_ast_collections_are_independent() -> None:
    first = ParsedAst(source=b"")
    second = ParsedAst(source=b"")
    first.symbols.append(Symbol(None, "function", ByteRange(0, 0), ByteRange(0, 0)))
    first.scope_graph.scopes.append(Scope(0, 0))

    assert not second.symbols
    assert not second.imports
    assert not second.scope_graph.scopes
