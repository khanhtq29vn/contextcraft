from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if node.type != "import_declaration" or any(
            child.type == "asterisk" for child in node.named_children
        ):
            return None
        name = node.named_children[-1]
        return _names([name.child_by_field_name("name") or name])
