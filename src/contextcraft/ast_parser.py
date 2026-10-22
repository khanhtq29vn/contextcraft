"""Shared Tree-sitter traversal and language-specific extraction dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from contextcraft.languages import get_extractor
from contextcraft.models import ASTParseResult, SymbolNode

if TYPE_CHECKING:
    from tree_sitter import Node

try:
    from tree_sitter_language_pack import get_parser

    HAS_TREE_SITTER = True
except ImportError:  # pragma: no cover
    HAS_TREE_SITTER = False


class UniversalASTParser:
    """Extracts architectural symbols, byte spans, and dependency references."""

    @classmethod
    def parse(cls, content: str, language_id: str) -> tuple[list[SymbolNode], list[str]]:
        """Parse source code into `(symbols, imports)`."""
        detailed = cls.parse_detailed(content, language_id)
        return detailed.symbols, detailed.imports

    @classmethod
    def parse_detailed(cls, content: str, language_id: str) -> ASTParseResult:
        """Parse symbols, imports, definitions, and identifier references."""
        if not content.strip():
            return ASTParseResult([], [], [], [])

        extractor = get_extractor(language_id)
        if not HAS_TREE_SITTER:
            return extractor.parse_fallback(content)

        try:
            parser = get_parser(language_id)
        except Exception:
            # Grammar loading can fail for unsupported, missing, or uncached grammars.
            return extractor.parse_fallback(content)

        source = content.encode("utf-8")
        tree = parser.parse(source)
        if not extractor.should_extract(tree.root_node):
            return extractor.parse_fallback(content)
        return cls._extract_from_tree(tree.root_node, source, language_id)

    @classmethod
    def _extract_from_tree(
        cls,
        root: Node,
        raw_bytes: bytes,
        language_id: str,
    ) -> ASTParseResult:
        extractor = get_extractor(language_id)
        symbols: list[SymbolNode] = []
        imports: dict[str, None] = {}
        definitions: dict[str, None] = {}
        references: dict[str, None] = {}

        def traverse(
            node: Node,
            parent_name: str | None = None,
            parent_type: str | None = None,
        ) -> None:
            scope = extractor.enclosing_scope(node, raw_bytes)
            if scope is not None:
                scope_name, parent_type = scope
                parent_name = f"{parent_name}.{scope_name}" if parent_name else scope_name

            declaration, decorators = extractor.unwrap_declaration(node, raw_bytes)
            if node.type in extractor.IMPORT_NODE_TYPES:
                text = cls._node_text(node, raw_bytes).strip()
                if text:
                    imports[text] = None

            kind = extractor.symbol_kind(declaration, parent_type)
            if kind is not None:
                record_symbol(declaration, node, kind, parent_name, parent_type, decorators)
                return

            if extractor.is_reference(node):
                name = cls._node_text(node, raw_bytes).strip()
                if len(name) >= 3:
                    references[name] = None

            for child in node.children:
                traverse(child, parent_name, parent_type)

        def record_symbol(
            node: Node,
            outer_node: Node,
            kind: str,
            parent_name: str | None,
            parent_type: str | None,
            decorators: list[str],
        ) -> None:
            if extractor.name_node(node) is None:
                for child in node.children:
                    traverse(child, parent_name, parent_type)
                return

            name = extractor.symbol_name(node, raw_bytes)
            if not name:
                return

            qualified_name = f"{parent_name}.{name}" if parent_name else name
            definitions[name] = None
            if parent_name:
                definitions[qualified_name] = None

            docstring, doc_range = extractor.extract_docstring(node, outer_node, raw_bytes)
            body_range = extractor.elidable_body_range(
                node, raw_bytes, doc_range.end_byte if doc_range is not None else None
            )
            symbols.append(
                SymbolNode(
                    name=name,
                    qualified_name=qualified_name,
                    kind=kind,
                    signature=extractor.extract_signature(node, outer_node, raw_bytes),
                    docstring=docstring,
                    full_range=extractor.node_range(outer_node),
                    body_range=body_range,
                    is_exported=extractor.is_exported(node, name, raw_bytes),
                    parent_symbol=parent_name,
                    decorators=decorators,
                )
            )
            for child in node.children:
                traverse(child, qualified_name, node.type)

        traverse(root)
        return ASTParseResult(
            symbols=symbols,
            imports=list(imports),
            defined_identifiers=list(definitions),
            referenced_identifiers=list(references),
        )

    @staticmethod
    def _node_text(node: Node, raw_bytes: bytes) -> str:
        return raw_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
