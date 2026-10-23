from __future__ import annotations

import ast

from contextcraft.ast import Import, ParsedAst
from contextcraft.languages.imports import ImportTrimmer as BaseImportTrimmer


class ImportTrimmer(BaseImportTrimmer):
    def trim(self, parsed: ParsedAst) -> list[Import]:
        if b"__all__" in parsed.source:
            return parsed.imports
        return super().trim(parsed)

    @staticmethod
    def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
        try:
            statement = ast.parse(declaration).body[0]
        except (SyntaxError, IndexError):
            return None
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            return None
        if isinstance(statement, ast.ImportFrom) and statement.module == "__future__":
            return None
        if any(alias.name == "*" or alias.asname == alias.name for alias in statement.names):
            return None
        return frozenset(alias.asname or alias.name.split(".")[0] for alias in statement.names)
