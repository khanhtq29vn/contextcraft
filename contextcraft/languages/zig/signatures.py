from __future__ import annotations

from dataclasses import replace

from contextcraft.ast import ParsedAst
from contextcraft.languages.structural import BlockSignaturesBuilder


class SignaturesBuilder(BlockSignaturesBuilder):
    closing = "};"

    def build(self, parsed: ParsedAst) -> str:
        # Keep static imports in their native scope, without duplicating public reexports.
        symbols = [
            replace(symbol, is_public=True)
            if symbol.kind in {"constant", "variable"}
            and any(
                symbol.declaration_range.start_byte <= item.declaration_range.start_byte
                and item.declaration_range.end_byte <= symbol.declaration_range.end_byte
                for item in parsed.imports
            )
            else symbol
            for symbol in parsed.symbols
        ]
        return super().build(replace(parsed, symbols=symbols))

    def _import_lines(self, parsed: ParsedAst) -> list[str]:
        return []
