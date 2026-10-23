from __future__ import annotations

from dataclasses import replace

from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.languages.structural import BlockSignaturesBuilder


class SignaturesBuilder(BlockSignaturesBuilder):
    opening = " do"
    closing = "end"

    def build(self, parsed: ParsedAst) -> str:
        # Directives such as use and alias must stay inside their enclosing module.
        directives: dict[ByteRange, Symbol] = {}
        for item in parsed.imports:
            enclosing = [
                symbol
                for symbol in parsed.symbols
                if symbol.declaration_range.start_byte <= item.declaration_range.start_byte
                and item.declaration_range.end_byte <= symbol.declaration_range.end_byte
            ]
            parent = min(
                enclosing,
                key=lambda symbol: (
                    symbol.declaration_range.end_byte - symbol.declaration_range.start_byte
                ),
                default=None,
            )
            directives[item.declaration_range] = Symbol(
                item.module,
                "directive",
                item.declaration_range,
                item.declaration_range,
                parent=parent,
            )
        symbols = sorted(
            [*parsed.symbols, *directives.values()],
            key=lambda symbol: symbol.declaration_range.start_byte,
        )
        return super().build(replace(parsed, symbols=symbols))

    def _import_lines(self, parsed: ParsedAst) -> list[str]:
        return []

    def _render_function(self, signature: str) -> str:
        if signature.endswith("do:"):
            return signature + " nil"
        return signature + " do\n nil\nend"
