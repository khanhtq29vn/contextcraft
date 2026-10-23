from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _descendants, _names, _parse_import


class ImportTrimmer(BaseImportTrimmer):
    case_sensitive = False

    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(
            parser_id,
            declaration,
            prefix="<?php\n",
            ignored_nodes=frozenset({"comment", "php_tag"}),
        )
        if node is None:
            return None
        if node.type != "namespace_use_declaration":
            return None
        bindings = []
        for clause in _descendants(node, "namespace_use_clause"):
            name = clause.child_by_field_name("alias") or clause.named_children[-1]
            bindings.append(name.named_children[-1] if name.type == "qualified_name" else name)
        return _names(bindings)
