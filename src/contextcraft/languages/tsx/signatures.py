from __future__ import annotations

from contextcraft.languages.javascript.imports import ImportTrimmer
from contextcraft.languages.structural import StructuralSignaturesBuilder


class SignaturesBuilder(StructuralSignaturesBuilder):
    import_trimmer = ImportTrimmer
