from __future__ import annotations

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _descendants, _names, _parse_import, _text


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if (
            node.type != "import_declaration"
            or _descendants(node, "namespace_wildcard")
            or any(child.type == "," for child in node.children)
        ):
            return None
        selectors = _descendants(node, "namespace_selectors")
        if selectors:
            bindings = []
            for child in selectors[0].named_children:
                if child.type == "identifier":
                    bindings.append(child)
                elif child.type in {"arrow_renamed_identifier", "as_renamed_identifier"}:
                    alias = child.child_by_field_name("alias")
                    if alias is None or _text(alias) == "_":
                        return None
                    bindings.append(alias)
                else:
                    return None
            return _names(bindings)
        alias = next(
            (child for child in node.named_children if child.type == "as_renamed_identifier"), None
        )
        if alias is not None:
            name = alias.child_by_field_name("alias")
            return _names([name]) if name is not None and _text(name) != "_" else None
        if any(child.type != "identifier" for child in node.named_children):
            return None
        paths = node.children_by_field_name("path")
        return _names(paths[-1:])
