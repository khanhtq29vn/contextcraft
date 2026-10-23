from __future__ import annotations

from contextcraft.ast import ByteRange, ParsedAst
from contextcraft.languages.structural import StructuralSkeletonBuilder


class SkeletonBuilder(StructuralSkeletonBuilder):
    def _replacements(self, parsed: ParsedAst) -> list[tuple[ByteRange, bytes]]:
        return [
            (
                symbol.body_range,
                b"do\n nil\nend"
                if parsed.text(symbol.body_range).split(maxsplit=1)[0] == "do"
                else b"nil",
            )
            for symbol in parsed.symbols
            if symbol.body_range is not None
        ]
