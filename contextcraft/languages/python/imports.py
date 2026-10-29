"""Extract Python import statements as language-independent records."""

from __future__ import annotations

import tree_sitter as ts

from contextcraft.models import Import


def _import_name(source: bytes, node: ts.Node) -> str:
    if node.type == "aliased_import":
        name = node.child_by_field_name("name")

        if name is None:
            return ""

        node = name

    return ".".join(
        source[child.start_byte : child.end_byte].decode("utf-8")
        for child in node.named_children
        if child.type == "identifier"
    )


def extract_imports(source: bytes, file_id: int, nodes: list[ts.Node]) -> list[Import]:
    """Return import records in source order, including nested imports.

    Args:
        source: UTF-8 Python source bytes to parse.
        file_id: Index file ID assigned to every returned record.
        nodes: Captured import statement nodes.

    Returns:
        Import records with original module names rather than aliases.
        Relative imports retain the number of leading dots, and wildcard
        imports use '*'. Statements with parse errors are skipped.
    """
    records = []

    for statement in sorted(nodes, key=lambda node: node.start_byte):
        if statement.has_error:
            continue

        names = tuple(
            name
            for node in statement.children_by_field_name("name")
            if (name := _import_name(source, node))
        )

        if statement.type == "import_statement":
            records.extend(
                Import(source_file_id=file_id, module_name=name) for name in names
            )
            continue

        module = statement.child_by_field_name("module_name")

        if module is None:
            continue

        relative_level = 0
        module_name = _import_name(source, module)

        if module.type == "relative_import":
            for child in module.named_children:
                if child.type == "import_prefix":
                    relative_level = source[child.start_byte : child.end_byte].count(
                        b"."
                    )
                elif child.type == "dotted_name":
                    module_name = _import_name(source, child)

        if any(child.type == "wildcard_import" for child in statement.named_children):
            names = ("*",)

        records.append(
            Import(
                source_file_id=file_id,
                module_name=module_name,
                relative_level=relative_level,
                imported_names=names,
            )
        )

    return records
