from __future__ import annotations

from contextcraft.languages.structural import BlockSignaturesBuilder
from contextcraft.languages.swift.imports import ImportTrimmer


class SignaturesBuilder(BlockSignaturesBuilder):
    import_trimmer = ImportTrimmer
