"""Extract Python docstring values from Tree-sitter captures."""

from __future__ import annotations

from ast import literal_eval

import tree_sitter as ts


def extract_docstrings(source: bytes, nodes: list[ts.Node]) -> tuple[str, ...]:
    """Extract literal docstring values in source order.

    Args:
        source: UTF-8 Python source bytes.
        nodes: Captured docstring expression nodes.

    Returns:
        A tuple of evaluated strings in source order. Skip captures with
        syntax errors, expressions that cannot be evaluated as literals,
        and values that are not strings.
    """
    docstrings = []

    for node in sorted(nodes, key=lambda node: node.start_byte):
        if node.has_error:
            continue

        try:
            value = literal_eval(
                source[node.start_byte : node.end_byte].decode("utf-8")
            )
        except (SyntaxError, ValueError):
            continue

        if isinstance(value, str):
            docstrings.append(value)

    return tuple(docstrings)
