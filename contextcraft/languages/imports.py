from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from contextcraft.ast import Import, ParsedAst

if TYPE_CHECKING:
    from contextcraft.languages.base import LanguageSpec


class ImportTrimmer:
    case_sensitive: ClassVar[bool] = True

    def __init__(self, spec: LanguageSpec) -> None:
        self.spec = spec

    def trim(self, parsed: ParsedAst) -> list[Import]:
        if parsed.has_errors or not parsed.symbols:
            return parsed.imports
        declarations = "\n".join(parsed.text(symbol.signature_range) for symbol in parsed.symbols)
        names = set(re.findall(r"\b[^\W\d]\w*\b", declarations))
        names.update(
            reference.name
            for reference in parsed.scope_graph.references
            if reference.scope.kind == "module"
            and not any(
                item.declaration_range.start_byte
                <= reference.start_byte
                < item.declaration_range.end_byte
                for item in parsed.imports
            )
        )
        if not self.case_sensitive:
            names = {name.casefold() for name in names}
        return [
            item
            for item in parsed.imports
            if (
                bindings := self._cached_bindings(
                    self.spec.parser_id, parsed.text(item.declaration_range)
                )
            )
            is None
            or any((name if self.case_sensitive else name.casefold()) in names for name in bindings)
        ]

    @classmethod
    @lru_cache(maxsize=2048)
    def _cached_bindings(cls, parser_id: str | None, declaration: str) -> frozenset[str] | None:
        return cls._bindings(parser_id, declaration)

    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        # Unknown bindings or side effects must preserve the import.
        return None


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8")


def _names(nodes: list[Node]) -> frozenset[str] | None:
    names = frozenset(_text(node) for node in nodes)
    if not names or any(not re.fullmatch(r"[^\W\d]\w*", name) for name in names):
        return None
    return names


def _descendants(node: Node, kind: str) -> list[Node]:
    found = []
    pending = [node]
    while pending:
        child = pending.pop()
        if child.type == kind:
            found.append(child)
        pending.extend(reversed(child.named_children))
    return found


def _parse_import(
    parser_id: str | None,
    declaration: str,
    *,
    prefix: str = "",
    ignored_nodes: frozenset[str] = frozenset({"comment"}),
) -> Node | None:
    if parser_id is None:
        return None
    try:
        root = get_parser(parser_id).parse((prefix + declaration).encode("utf-8")).root_node
    except Exception:
        return None
    if root.has_error:
        return None
    nodes = [node for node in root.named_children if node.type not in ignored_nodes]
    return nodes[0] if len(nodes) == 1 else None
