from __future__ import annotations

from contextcraft.ast import ParsedAst, Symbol
from contextcraft.languages.base import SignaturesBuilder as BaseSignaturesBuilder
from contextcraft.languages.javascript.imports import ImportTrimmer


class SignaturesBuilder(BaseSignaturesBuilder):
    import_trimmer = ImportTrimmer

    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        lines = self._import_lines(parsed)
        classes: list[Symbol] = []

        for symbol in parsed.symbols:
            if symbol.name is None or symbol.name.startswith(("_", "#")):
                continue
            parent = symbol.parent
            while parent is not None:
                if (
                    parent.kind != "class"
                    or parent.name is None
                    or parent.name.startswith(("_", "#"))
                ):
                    break
                parent = parent.parent
            if parent is not None:
                continue

            while classes and symbol.parent is not classes[-1]:
                classes.pop()
                lines.append("    " * len(classes) + "};")

            indent = "    " * len(classes)
            signature = parsed.text(symbol.signature_range)
            prefix = "" if classes else "const "
            if symbol.kind == "class":
                lines.append(f"{indent}{prefix}{symbol.name} = {signature} {{")
                classes.append(symbol)
            elif symbol.kind == "method":
                lines.append(f"{indent}{signature} {{}}")
            else:
                lines.append(f"{indent}{prefix}{symbol.name} = {signature} {{}};")

        while classes:
            classes.pop()
            lines.append("    " * len(classes) + "};")

        return "\n".join(lines) + "\n" if lines else ""
