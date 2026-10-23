from __future__ import annotations

from contextcraft.ast import ByteRange, ParsedAst
from contextcraft.languages.structural import StructuralSkeletonBuilder


class SkeletonBuilder(StructuralSkeletonBuilder):
    marker = b"<!-- ... -->"

    def _replacements(self, parsed: ParsedAst) -> list[tuple[ByteRange, bytes]]:
        edits = super()._replacements(parsed)
        for region in parsed.embedded_regions:
            builder = region.language.skeleton_builder(region.language.spec)
            edits.append((region.source_range, builder.build(region.parsed).encode("utf-8")))
        return edits
