from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if node.type != "using_directive" or any(child.type == "global" for child in node.children):
            return None
        name = node.child_by_field_name("name")
        return _names([name]) if name is not None else None
