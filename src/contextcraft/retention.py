from __future__ import annotations

from collections import Counter
from functools import lru_cache

from contextcraft.ast import ParsedAst, Symbol
from contextcraft.ast.parser import parse
from contextcraft.languages.base import Language
from contextcraft.languages.builtin import default_registry
from contextcraft.models import FileAnalysis

CODE_SYMBOL_KINDS = frozenset(
    {
        "class",
        "constructor",
        "enum",
        "function",
        "interface",
        "method",
        "struct",
        "trait",
        "type",
        "type_alias",
    }
)


def code_symbols(parsed: ParsedAst, *, public_only: bool = True) -> list[Symbol]:
    symbols = []
    for symbol in parsed.symbols:
        if symbol.name is None or symbol.kind not in CODE_SYMBOL_KINDS:
            continue
        if public_only and not symbol.is_public:
            continue
        parent = symbol.parent
        while parent is not None:
            if parent.kind in {"function", "method", "constructor"} or (
                public_only and not parent.is_public
            ):
                break
            parent = parent.parent
        if parent is None:
            symbols.append(symbol)
    return symbols


@lru_cache(maxsize=64)
def _default_language(language_id: str) -> type[Language] | None:
    return default_registry().get(language_id)


def retained_symbols(
    file: FileAnalysis,
    content: str,
    *,
    language: type[Language] | None = None,
    public_only: bool = True,
) -> list[Symbol]:
    symbols = code_symbols(file.parsed, public_only=public_only)
    if not symbols or not content.strip():
        return []
    source = content.encode("utf-8")
    if source == file.parsed.source:
        return symbols
    language = language or _default_language(file.language)
    if language is None:
        return []

    # Matching declaration context prevents A.run from also crediting an omitted B.run.
    rendered = parse(source, language)
    available = Counter(
        (
            symbol.kind,
            symbol.qualified_name,
            " ".join(rendered.text(symbol.signature_range).split()),
        )
        for symbol in rendered.symbols
        if symbol.name is not None and symbol.kind in CODE_SYMBOL_KINDS
    )
    retained = []
    for symbol in symbols:
        signature = " ".join(file.parsed.text(symbol.signature_range).split())
        if not signature:
            continue
        for key, count in available.items():
            kind, name, rendered_signature = key
            if (
                count
                and kind == symbol.kind
                and name == symbol.qualified_name
                and signature in rendered_signature
            ):
                available[key] -= 1
                retained.append(symbol)
                break
    return retained
