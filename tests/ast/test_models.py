from __future__ import annotations

from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.ast.scope import Binding, Reference, Scope


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


def test_symbol_qualified_names_follow_direct_parent_links() -> None:
    span = ByteRange(0, 0)
    parent = Symbol("Client", "class", span, span)
    child = Symbol("fetch", "method", span, span, parent=parent)
    parsed = ParsedAst(source=b"", symbols=[parent, child])

    assert child.qualified_name == "Client.fetch"
    assert parsed.defined_identifiers == ["Client", "fetch", "Client.fetch"]
