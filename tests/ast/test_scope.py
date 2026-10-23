from __future__ import annotations

from contextcraft.ast.scope import Binding, Scope


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
