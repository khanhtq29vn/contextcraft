from __future__ import annotations

import re

from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer
from contextcraft.languages.imports import _descendants, _parse_import, _text


class ImportTrimmer(BaseImportTrimmer):
    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        node = _parse_import(
            parser_id,
            declaration,
            prefix="package p\n",
            ignored_nodes=frozenset({"comment", "package_clause"}),
        )
        if node is None:
            return None
        packages: set[str] = set()
        for item in _descendants(node, "import_spec"):
            name = item.child_by_field_name("name")
            if name is not None:
                if _text(name) in {"_", "."}:
                    return None
                packages.add(_text(name))
            else:
                path = item.child_by_field_name("path")
                if path is None:
                    return None
                path_text = _text(path).strip('"`')
                # External and versioned package names may differ from their paths.
                if (
                    "." in path_text
                    or path_text == "C"
                    or re.fullmatch(r"v\d+", path_text.rsplit("/", 1)[-1])
                ):
                    return None
                packages.add(path_text.rsplit("/", 1)[-1])
        return frozenset(packages) or None
