from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Binding:
    name: str
    start_byte: int
    end_byte: int
    scope: Scope = field(repr=False, compare=False)


@dataclass(frozen=True)
class Reference:
    name: str
    start_byte: int
    end_byte: int
    scope: Scope = field(repr=False, compare=False)


@dataclass
class Scope:
    start_byte: int
    end_byte: int
    parent: Scope | None = field(default=None, repr=False)
    kind: str = "block"
    bindings: dict[str, Binding] = field(default_factory=dict)
    references: list[Reference] = field(default_factory=list)

    def resolve(self, name: str) -> Binding | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.bindings:
                return scope.bindings[name]
            scope = scope.parent
        return None


@dataclass
class ScopeGraph:
    scopes: list[Scope] = field(default_factory=list)
    bindings: list[Binding] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
