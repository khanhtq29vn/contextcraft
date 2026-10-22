from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from contextcraft.ast.scope import ScopeGraph

if TYPE_CHECKING:
    from contextcraft.languages.base import Language


@dataclass(frozen=True)
class ByteRange:
    start_byte: int
    end_byte: int


@dataclass(frozen=True)
class Symbol:
    name: str | None
    kind: str
    declaration_range: ByteRange
    signature_range: ByteRange
    body_range: ByteRange | None = None
    docstring_range: ByteRange | None = None
    parent: Symbol | None = field(default=None, repr=False, compare=False)
    is_public: bool = True

    @property
    def qualified_name(self) -> str | None:
        if self.name is None:
            return None
        parent_name = self.parent.qualified_name if self.parent is not None else None
        return f"{parent_name}.{self.name}" if parent_name else self.name


@dataclass(frozen=True)
class Import:
    module: str
    declaration_range: ByteRange


@dataclass(frozen=True)
class EmbeddedRegion:
    source_range: ByteRange
    language: type[Language]
    parsed: ParsedAst


@dataclass
class ParsedAst:
    source: bytes
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    scope_graph: ScopeGraph = field(default_factory=ScopeGraph)
    has_errors: bool = False
    embedded_regions: list[EmbeddedRegion] = field(default_factory=list)

    def text(self, span: ByteRange) -> str:
        return self.source[span.start_byte : span.end_byte].decode("utf-8")

    @property
    def defined_identifiers(self) -> list[str]:
        names = dict.fromkeys(binding.name for binding in self.scope_graph.bindings)
        for symbol in self.symbols:
            if symbol.name is not None:
                names[symbol.name] = None
            if symbol.qualified_name is not None:
                names[symbol.qualified_name] = None
        return list(names)

    @property
    def referenced_identifiers(self) -> list[str]:
        return list(dict.fromkeys(ref.name for ref in self.scope_graph.references))
