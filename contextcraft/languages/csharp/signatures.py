from __future__ import annotations

from contextcraft.languages.csharp.imports import ImportTrimmer
from contextcraft.languages.structural import StructuralSignaturesBuilder


class SignaturesBuilder(StructuralSignaturesBuilder):
    import_trimmer = ImportTrimmer
