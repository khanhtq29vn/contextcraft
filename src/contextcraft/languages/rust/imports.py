from __future__ import annotations

from contextcraft.ast import Import, ParsedAst
from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _names, _parse_import, _text


class ImportTrimmer(BaseImportTrimmer):
    def trim(self, parsed: ParsedAst) -> list[Import]:
        if b"macro_use" in parsed.source:
            return parsed.imports
        return super().trim(parsed)

    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(parser_id, declaration)
        if node is None:
            return None
        if any(child.type == "visibility_modifier" for child in node.named_children):
            return None
        if node.type == "extern_crate_declaration":
            name = node.child_by_field_name("alias") or node.child_by_field_name("name")
            return _names([name]) if name is not None and _text(name) != "_" else None
        if node.type != "use_declaration":
            return None
        bindings = []
        pending = [node.child_by_field_name("argument")]
        while pending:
            part = pending.pop()
            if part is None:
                return None
            if part.type in {"use_wildcard", "self"}:
                return None
            if part.type in {"identifier", "scoped_identifier", "use_as_clause"}:
                name = part.child_by_field_name("alias") or part.child_by_field_name("name") or part
                if _text(name) in {"_", "self"}:
                    return None
                bindings.append(name)
            elif part.type == "scoped_use_list":
                pending.append(part.child_by_field_name("list"))
            elif part.type == "use_list":
                pending.extend(part.named_children)
            else:
                return None
        return _names(bindings)
