from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if node.type != "import_statement":
            return None
        clause = next(
            (
                child
                for child in node.named_children
                if child.type in {"import_clause", "import_require_clause"}
            ),
            None,
        )
        if clause is None:
            return None
        bindings = []
        for child in clause.named_children:
            if child.type == "identifier":
                bindings.append(child)
            elif child.type == "namespace_import":
                bindings.extend(child.named_children)
            elif child.type == "named_imports":
                for item in child.named_children:
                    name = item.child_by_field_name("alias") or item.child_by_field_name("name")
                    if name is None:
                        return None
                    bindings.append(name)
            elif child.type != "string":
                return None
        return _names(bindings)
