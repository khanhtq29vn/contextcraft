from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _descendants, _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        headers = _descendants(node, "import_header")
        if len(headers) != 1:
            return None
        header = headers[0]
        if any(child.type == "wildcard_import" for child in header.named_children):
            return None
        alias = next(
            (child for child in header.named_children if child.type == "import_alias"), None
        )
        path = next((child for child in header.named_children if child.type == "identifier"), None)
        name = alias or path
        return (
            _names([name.named_children[-1]]) if name is not None and name.named_children else None
        )
