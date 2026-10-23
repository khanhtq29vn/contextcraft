from __future__ import annotations

from contextcraft.ast import ParsedAst
from contextcraft.languages.base import SkeletonBuilder as BaseSkeletonBuilder


class SkeletonBuilder(BaseSkeletonBuilder):
    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        candidates = sorted(
            (
                symbol.body_range
                for symbol in parsed.symbols
                if symbol.kind in {"function", "method"} and symbol.body_range is not None
            ),
            key=lambda span: (span.start_byte, -span.end_byte),
        )
        spans = []
        covered_until = 0

        for span in candidates:
            if span.start_byte < covered_until:
                continue
            body = parsed.source[span.start_byte : span.end_byte]
            if body.startswith(b"{") and body.endswith(b"}") and not body[1:-1].strip():
                continue
            spans.append(span)
            covered_until = span.end_byte

        buffer = bytearray(parsed.source)
        for span in reversed(spans):
            buffer[span.start_byte : span.end_byte] = b"{ /* ... */ }"
        return buffer.decode("utf-8")
