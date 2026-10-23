from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _descendants, _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if node.type != "import_declaration" or any(
            child.type == "modifiers" for child in node.named_children
        ):
            return None
        if not any(
            child.type in {"typealias", "struct", "class", "enum", "protocol", "let", "var", "func"}
            for child in node.children
        ):
            return None
        identifiers = _descendants(node, "simple_identifier")
        return _names(identifiers[-1:])
