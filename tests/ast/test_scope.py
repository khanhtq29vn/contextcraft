from __future__ import annotations

from contextcraft.ast.scope import Binding, Reference, Scope, ScopeGraph


def test_scope_resolves_bindings_and_shadowing() -> None:
    outer = Scope(0, 100)
    outer_binding = Binding("value", 0, 5, outer)
    outer.bindings["value"] = outer_binding
    inner = Scope(10, 50, parent=outer)

    assert inner.resolve("value") is outer_binding
    assert inner.resolve("missing") is None

    inner_binding = Binding("value", 12, 17, inner)
    inner.bindings["value"] = inner_binding

    assert inner.resolve("value") is inner_binding
    assert outer.resolve("value") is outer_binding


def test_scope_collections_are_independent() -> None:
    first = Scope(0, 10)
    second = Scope(10, 20)
    reference = Reference("value", 2, 7, first)
    first.references.append(reference)
    first.bindings["value"] = Binding("value", 0, 1, first)

    assert first.references == [reference]
    assert not second.references
    assert not second.bindings
    assert second.resolve("value") is None


def test_scope_graph_collections_are_independent() -> None:
    first = ScopeGraph()
    second = ScopeGraph()
    scope = Scope(0, 10)
    first.scopes.append(scope)
    first.bindings.append(Binding("value", 0, 1, scope))
    first.references.append(Reference("value", 2, 7, scope))

    assert not second.scopes
    assert not second.bindings
    assert not second.references
