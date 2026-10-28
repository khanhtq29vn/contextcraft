"""Pair source text with a Tree-sitter parse tree."""

import tree_sitter as ts


class Document:
    """Keep source text alongside its parse tree without checking that they match.

    Args:
        source: Source text represented by the tree.
        tree: Tree-sitter tree parsed from the source's encoded bytes.
    """

    def __init__(self, source: str, tree: ts.Tree) -> None:
        self.source = source
        self.tree = tree
