from __future__ import annotations

from contextcraft.languages.java.imports import ImportTrimmer
from contextcraft.languages.structural import BlockSignaturesBuilder


class SignaturesBuilder(BlockSignaturesBuilder):
    import_trimmer = ImportTrimmer
