from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import ClassVar, Protocol

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from contextcraft.ast import ParsedAst, Symbol
from contextcraft.ast.scope import ScopeGraph
from contextcraft.languages.imports import ImportTrimmer


@dataclass(frozen=True)
class LanguageSpec:
    id: str
    extensions: frozenset[str] = frozenset()
    filenames: frozenset[str] = frozenset()
    ignore_patterns: tuple[str, ...] = ()
    parser_id: str | None = None
    aliases: tuple[str, ...] = ()


class ASTExtractor(Protocol):
    def extract(
        self,
        root: Node,
        source: bytes,
    ) -> ParsedAst: ...

    def build_scopes(self, root: Node, source: bytes) -> ScopeGraph: ...


class BaseExtractor:
    def extract(self, root: Node, source: bytes) -> ParsedAst:
        graph = self.build_scopes(root, source)
        return ParsedAst(source=source, scope_graph=graph, has_errors=root.has_error)

    def build_scopes(self, root: Node, source: bytes) -> ScopeGraph:
        raise NotImplementedError


class SkeletonBuilder(ABC):
    def __init__(self, spec: LanguageSpec) -> None:
        self.spec = spec

    @abstractmethod
    def build(self, parsed: ParsedAst) -> str:
        raise NotImplementedError


class SignaturesBuilder(ABC):
    import_trimmer: ClassVar[type[ImportTrimmer]] = ImportTrimmer

    def __init__(self, spec: LanguageSpec) -> None:
        self.spec = spec

    @abstractmethod
    def build(self, parsed: ParsedAst) -> str:
        raise NotImplementedError

    def _import_lines(self, parsed: ParsedAst) -> list[str]:
        return list(
            dict.fromkeys(
                parsed.text(item.declaration_range)
                for item in self.import_trimmer(self.spec).trim(parsed)
            )
        )

    def build_selected(self, parsed: ParsedAst, symbols: list[Symbol]) -> str:
        """Render selected declarations with their enclosing type context."""
        selected = {id(symbol) for symbol in symbols}
        for symbol in symbols:
            parent = symbol.parent
            while parent is not None:
                selected.add(id(parent))
                parent = parent.parent
        return self.build(
            replace(parsed, symbols=[symbol for symbol in parsed.symbols if id(symbol) in selected])
        )


class Language:
    spec: ClassVar[LanguageSpec]
    extractor: ClassVar[type[ASTExtractor]]
    skeleton_builder: ClassVar[type[SkeletonBuilder]]
    signatures_builder: ClassVar[type[SignaturesBuilder]]

    @classmethod
    def parse(cls, root: Node, source: bytes) -> ParsedAst:
        return cls.extractor().extract(root, source)

    @classmethod
    def build_selected(cls, parsed: ParsedAst, symbols: list[Symbol]) -> str:
        """Render a subset, falling back to body-elided native source when needed."""
        content = cls.signatures_builder(cls.spec).build_selected(parsed, symbols)
        if cls.spec.parser_id is None or parsed.has_errors:
            return content
        try:
            parser = get_parser(cls.spec.parser_id)
        except Exception:
            return content
        if not parser.parse(content.encode("utf-8")).root_node.has_error:
            return content

        # Preserve native container syntax (including namespaces and impl blocks)
        # when a compact builder cannot represent a selected declaration safely.
        selected = {id(symbol) for symbol in symbols}
        for symbol in symbols:
            parent = symbol.parent
            while parent is not None:
                selected.add(id(parent))
                parent = parent.parent
        spans = sorted(
            (symbol.declaration_range for symbol in parsed.symbols if id(symbol) not in selected),
            key=lambda span: (span.start_byte, -span.end_byte),
        )
        edits = []
        end = -1
        for span in spans:
            if span.start_byte >= end:
                edits.append(span)
                end = span.end_byte
        source = bytearray(parsed.source)
        for span in reversed(edits):
            source[span.start_byte : span.end_byte] = b""
        root = parser.parse(bytes(source)).root_node
        if root.has_error:
            return content
        return cls.skeleton_builder(cls.spec).build(cls.parse(root, bytes(source)))

    @classmethod
    def build_scopes(cls, root: Node, source: bytes) -> ScopeGraph:
        return cls.extractor().build_scopes(root, source)
