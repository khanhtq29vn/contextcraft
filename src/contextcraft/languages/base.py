from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Protocol

from tree_sitter import Node

from contextcraft.ast import ParsedAst
from contextcraft.ast.scope import ScopeGraph


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
    def __init__(self, spec: LanguageSpec) -> None:
        self.spec = spec

    @abstractmethod
    def build(self, parsed: ParsedAst) -> str:
        raise NotImplementedError


class Language:
    spec: ClassVar[LanguageSpec]
    extractor: ClassVar[type[ASTExtractor]]
    skeleton_builder: ClassVar[type[SkeletonBuilder]]
    signatures_builder: ClassVar[type[SignaturesBuilder]]

    @classmethod
    def parse(cls, root: Node, source: bytes) -> ParsedAst:
        return cls.extractor().extract(root, source)

    @classmethod
    def build_scopes(cls, root: Node, source: bytes) -> ScopeGraph:
        return cls.extractor().build_scopes(root, source)
