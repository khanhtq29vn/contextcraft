"""Universal Tree-sitter AST parser and cross-file reference extractor.

Extracts classes, functions, methods, interfaces, structs, enums, docstrings,
and cross-file import/identifier references across major programming languages.
Includes a deterministic indentation/brace fallback parser so ContextCraft
never crashes even when a Tree-sitter grammar binary is unavailable.
"""

from __future__ import annotations

import keyword
import re
from typing import Any, ClassVar, NamedTuple

from contextcraft.models import ByteRange, SymbolKind, SymbolNode

try:
    from tree_sitter import Node, Tree
    from tree_sitter_language_pack import get_parser

    HAS_TREE_SITTER = True
except ImportError:  # pragma: no cover
    Node = Any  # type: ignore[misc,assignment]
    Tree = Any  # type: ignore[misc,assignment]
    HAS_TREE_SITTER = False


class ASTParseResult(NamedTuple):
    """Comprehensive structural output for a single source file."""

    symbols: list[SymbolNode]
    imports: list[str]
    defined_identifiers: list[str]
    referenced_identifiers: list[str]


class UniversalASTParser:
    """Extracts architectural symbols, byte spans, and dependency references."""

    _NODE_KIND_MAP: ClassVar[dict[str, SymbolKind]] = {
        "class_definition": SymbolKind.CLASS,
        "class_declaration": SymbolKind.CLASS,
        "class_specifier": SymbolKind.CLASS,
        "function_definition": SymbolKind.FUNCTION,
        "function_declaration": SymbolKind.FUNCTION,
        "function_item": SymbolKind.FUNCTION,
        "arrow_function": SymbolKind.FUNCTION,
        "method_definition": SymbolKind.METHOD,
        "method_declaration": SymbolKind.METHOD,
        "interface_declaration": SymbolKind.INTERFACE,
        "type_alias_declaration": SymbolKind.TYPE_ALIAS,
        "type_item": SymbolKind.TYPE_ALIAS,
        "struct_specifier": SymbolKind.STRUCT,
        "struct_item": SymbolKind.STRUCT,
        "struct_declaration": SymbolKind.STRUCT,
        "enum_declaration": SymbolKind.ENUM,
        "enum_specifier": SymbolKind.ENUM,
        "enum_item": SymbolKind.ENUM,
    }

    _BODY_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "block",
            "statement_block",
            "declaration_list",
            "class_body",
            "interface_body",
            "enum_body",
            "field_declaration_list",
            "compound_statement",
        }
    )

    _IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "import_statement",
            "import_from_statement",
            "import_declaration",
            "use_declaration",
            "preproc_include",
            "package_clause",
        }
    )

    _COMMON_STOPWORDS: ClassVar[frozenset[str]] = frozenset(
        set(keyword.kwlist)
        | {
            "self",
            "cls",
            "this",
            "super",
            "true",
            "false",
            "null",
            "none",
            "undefined",
            "void",
            "int",
            "str",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "any",
            "string",
            "number",
            "boolean",
            "object",
            "return",
            "async",
            "await",
            "const",
            "let",
            "var",
            "function",
            "class",
            "interface",
            "type",
            "export",
            "import",
            "from",
            "pub",
            "fn",
            "impl",
            "struct",
            "enum",
            "mut",
            "func",
            "package",
            "public",
            "private",
            "protected",
            "static",
            "final",
        }
    )

    _IDENTIFIER_RE: ClassVar[re.Pattern[str]] = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")

    @classmethod
    def parse(cls, content: str, language_id: str) -> tuple[list[SymbolNode], list[str]]:
        """Parse source code into `(symbols, imports)`."""
        detailed = cls.parse_detailed(content, language_id)
        return detailed.symbols, detailed.imports

    @classmethod
    def parse_detailed(cls, content: str, language_id: str) -> ASTParseResult:
        """Parse source code into symbols, imports, definitions, and identifier references."""
        if not content.strip():
            return ASTParseResult(
                symbols=[],
                imports=[],
                defined_identifiers=[],
                referenced_identifiers=[],
            )

        if not HAS_TREE_SITTER or language_id in {"unknown", "markdown", "json", "yaml", "toml"}:
            return cls._fallback_parse_detailed(content, language_id)

        ts_lang = "typescript" if language_id == "tsx" else language_id
        try:
            parser = get_parser(ts_lang)  # type: ignore[arg-type]
            raw_bytes = content.encode("utf-8")
            tree: Tree = parser.parse(raw_bytes)
            result = cls._extract_from_tree(tree.root_node, raw_bytes, language_id)
            if not result.symbols and language_id in {
                "python",
                "typescript",
                "tsx",
                "javascript",
                "rust",
                "go",
            }:
                # If Tree-sitter grammar yielded nothing on non-empty code, try fallback
                fallback = cls._fallback_parse_detailed(content, language_id)
                if fallback.symbols:
                    return fallback
            return result
        except Exception:
            return cls._fallback_parse_detailed(content, language_id)

    @classmethod
    def _extract_from_tree(
        cls,
        root: Node,
        raw_bytes: bytes,
        language_id: str,
    ) -> ASTParseResult:
        symbols: list[SymbolNode] = []
        imports: list[str] = []
        seen_imports: set[str] = set()
        defined_idents: list[str] = []
        seen_defined: set[str] = set()
        referenced_idents: list[str] = []
        seen_referenced: set[str] = set()

        def _add_defined(ident: str) -> None:
            if ident and ident not in seen_defined:
                seen_defined.add(ident)
                defined_idents.append(ident)

        def _add_referenced(ident: str) -> None:
            if (
                ident
                and len(ident) >= 3
                and ident not in cls._COMMON_STOPWORDS
                and ident not in seen_referenced
            ):
                seen_referenced.add(ident)
                referenced_idents.append(ident)

        def traverse(
            node: Node,
            parent_name: str | None = None,
            pending_decorators: list[str] | None = None,
        ) -> None:
            node_type = node.type

            # 1. Handle decorated definitions in Python / TypeScript
            if node_type == "decorated_definition":
                decs: list[str] = []
                target_child: Node | None = None
                for child in node.children:
                    if child.type == "decorator":
                        decs.append(cls._node_text(child, raw_bytes).strip())
                    elif child.type in cls._NODE_KIND_MAP:
                        target_child = child
                if target_child is not None:
                    cls._record_symbol_node(
                        node=target_child,
                        outer_node=node,
                        raw_bytes=raw_bytes,
                        language_id=language_id,
                        parent_name=parent_name,
                        decorators=decs,
                        symbols=symbols,
                        add_defined=_add_defined,
                        traverse_fn=traverse,
                    )
                    return

            # 2. Handle import statements
            if node_type in cls._IMPORT_NODE_TYPES or "import" in node_type:
                imp_text = cls._node_text(node, raw_bytes).strip()
                if imp_text and imp_text not in seen_imports:
                    seen_imports.add(imp_text)
                    imports.append(imp_text)
                for ident_match in cls._IDENTIFIER_RE.finditer(imp_text):
                    _add_referenced(ident_match.group(0))
                return

            # 3. Handle structural symbol definitions
            if node_type in cls._NODE_KIND_MAP:
                cls._record_symbol_node(
                    node=node,
                    outer_node=node,
                    raw_bytes=raw_bytes,
                    language_id=language_id,
                    parent_name=parent_name,
                    decorators=pending_decorators or [],
                    symbols=symbols,
                    add_defined=_add_defined,
                    traverse_fn=traverse,
                )
                return

            # 4. Collect identifier references
            if node_type in {"identifier", "type_identifier", "property_identifier"}:
                ident_text = cls._node_text(node, raw_bytes).strip()
                _add_referenced(ident_text)

            for child in node.children:
                traverse(child, parent_name, None)

        traverse(root)

        # Ensure references don't duplicate symbols solely defined in the same file unless referenced
        return ASTParseResult(
            symbols=symbols,
            imports=imports,
            defined_identifiers=defined_idents,
            referenced_identifiers=referenced_idents,
        )

    @classmethod
    def _record_symbol_node(
        cls,
        *,
        node: Node,
        outer_node: Node,
        raw_bytes: bytes,
        language_id: str,
        parent_name: str | None,
        decorators: list[str],
        symbols: list[SymbolNode],
        add_defined: Any,
        traverse_fn: Any,
    ) -> None:
        raw_kind = cls._NODE_KIND_MAP[node.type]
        kind = (
            SymbolKind.METHOD
            if raw_kind == SymbolKind.FUNCTION and parent_name is not None
            else raw_kind
        )

        name_node = cls._find_name_node(node)
        body_node = cls._find_body_node(node)

        if name_node is None:
            for child in node.children:
                traverse_fn(child, parent_name, None)
            return

        name_str = cls._node_text(name_node, raw_bytes).strip()
        if not name_str:
            return

        qualified_name = f"{parent_name}.{name_str}" if parent_name else name_str
        add_defined(name_str)
        if parent_name:
            add_defined(qualified_name)

        docstring, doc_end_byte, doc_end_line = cls._extract_docstring(
            node=node,
            outer_node=outer_node,
            body_node=body_node,
            raw_bytes=raw_bytes,
            language_id=language_id,
        )

        full_range = ByteRange(
            start_byte=outer_node.start_byte,
            end_byte=outer_node.end_byte,
            start_line=outer_node.start_point[0] + 1,
            end_line=outer_node.end_point[0] + 1,
        )

        body_range = cls._compute_elidable_body_range(
            kind=kind,
            body_node=body_node,
            doc_end_byte=doc_end_byte,
            doc_end_line=doc_end_line,
            raw_bytes=raw_bytes,
            language_id=language_id,
        )

        sig_end_byte = body_node.start_byte if body_node is not None else node.end_byte
        signature_raw = raw_bytes[outer_node.start_byte : sig_end_byte].decode(
            "utf-8", errors="replace"
        )
        signature = signature_raw.strip().rstrip(":").rstrip("{").strip()

        is_exported = not name_str.startswith("_")
        if language_id == "go" and name_str:
            is_exported = name_str[0].isupper()

        symbols.append(
            SymbolNode(
                name=name_str,
                qualified_name=qualified_name,
                kind=kind,
                signature=signature,
                docstring=docstring,
                full_range=full_range,
                body_range=body_range,
                is_exported=is_exported,
                parent_symbol=parent_name,
                decorators=decorators,
            )
        )

        # Recurse into children to capture methods inside classes/structs/impls
        for child in node.children:
            traverse_fn(child, qualified_name, None)

    @classmethod
    def _find_name_node(cls, node: Node) -> Node | None:
        name_field = node.child_by_field_name("name")
        if name_field is not None:
            return name_field
        for child in node.children:
            if child.type in {"identifier", "type_identifier", "field_identifier", "property_identifier"}:
                return child
        return None

    @classmethod
    def _find_body_node(cls, node: Node) -> Node | None:
        body_field = node.child_by_field_name("body")
        if body_field is not None:
            return body_field
        for child in node.children:
            if child.type in cls._BODY_NODE_TYPES:
                return child
        return None

    @classmethod
    def _extract_docstring(
        cls,
        *,
        node: Node,
        outer_node: Node,
        body_node: Node | None,
        raw_bytes: bytes,
        language_id: str,
    ) -> tuple[str | None, int | None, int | None]:
        """Return `(docstring_text, docstring_end_byte, docstring_end_line)`."""
        # 1. Python docstring: first non-comment statement inside block is a string literal
        if language_id == "python" and body_node is not None:
            for child in body_node.children:
                if child.type in {"comment", "newline", "indent", ":"}:
                    continue
                if child.type == "expression_statement" and child.children:
                    first_expr = child.children[0]
                    if first_expr.type in {"string", "concatenated_string"}:
                        doc_text = cls._node_text(child, raw_bytes).strip()
                        return doc_text, child.end_byte, child.end_point[0] + 1
                if child.type in {"string", "concatenated_string"}:
                    doc_text = cls._node_text(child, raw_bytes).strip()
                    return doc_text, child.end_byte, child.end_point[0] + 1
                break

        # 2. Preceding doc-comment block (JSDoc /** ... */, Rust ///, Go //)
        prev = outer_node.prev_named_sibling
        comment_chunks: list[str] = []
        while prev is not None and "comment" in prev.type:
            # Only attach comment if it is immediately adjacent (within 1 line)
            if outer_node.start_point[0] - prev.end_point[0] <= 2:
                comment_chunks.append(cls._node_text(prev, raw_bytes).strip())
                outer_node = prev
                prev = prev.prev_named_sibling
            else:
                break

        if comment_chunks:
            comment_chunks.reverse()
            return "\n".join(comment_chunks), None, None

        return None, None, None

    @classmethod
    def _compute_elidable_body_range(
        cls,
        *,
        kind: SymbolKind,
        body_node: Node | None,
        doc_end_byte: int | None,
        doc_end_line: int | None,
        raw_bytes: bytes,
        language_id: str,
    ) -> ByteRange | None:
        """Compute the exact byte span of a function/method body to elide in Tier 2.

        Classes, interfaces, and structs have `body_range = None` so their member
        methods can be individually retained or elided without wiping out the class!
        """
        if body_node is None or kind not in {SymbolKind.FUNCTION, SymbolKind.METHOD}:
            return None

        if language_id == "python":
            # Start AFTER the docstring if present so Tier 2 preserves docstrings!
            for child in body_node.children:
                if child.type in {"comment", "newline", "indent", ":"}:
                    continue
                if doc_end_byte is not None and child.end_byte <= doc_end_byte:
                    continue
                # Found first executable statement after docstring
                if body_node.end_byte > child.start_byte:
                    return ByteRange(
                        start_byte=child.start_byte,
                        end_byte=body_node.end_byte,
                        start_line=child.start_point[0] + 1,
                        end_line=body_node.end_point[0] + 1,
                    )
            return None

        # Brace-delimited languages (TS, JS, Rust, Go, Java, C, C++):
        # body_node typically starts with '{' and ends with '}'
        body_text = cls._node_text(body_node, raw_bytes)
        if body_text.startswith("{") and body_text.endswith("}") and len(body_text) > 2:
            return ByteRange(
                start_byte=body_node.start_byte,
                end_byte=body_node.end_byte,
                start_line=body_node.start_point[0] + 1,
                end_line=body_node.end_point[0] + 1,
            )

        return None

    @staticmethod
    def _node_text(node: Node, raw_bytes: bytes) -> str:
        return raw_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    @classmethod
    def _fallback_parse_detailed(cls, content: str, language_id: str) -> ASTParseResult:
        """Indentation and brace-aware fallback parser when Tree-sitter is unavailable."""
        symbols: list[SymbolNode] = []
        imports: list[str] = []
        defined_idents: list[str] = []
        referenced_idents: list[str] = []

        lines = content.splitlines(keepends=True)
        line_byte_offsets: list[int] = [0]
        running_bytes = 0
        for line in lines:
            running_bytes += len(line.encode("utf-8"))
            line_byte_offsets.append(running_bytes)

        if language_id == "python":
            cls._fallback_python(
                lines=lines,
                line_byte_offsets=line_byte_offsets,
                symbols=symbols,
                imports=imports,
                defined_idents=defined_idents,
            )
        else:
            cls._fallback_c_family(
                content=content,
                lines=lines,
                line_byte_offsets=line_byte_offsets,
                language_id=language_id,
                symbols=symbols,
                imports=imports,
                defined_idents=defined_idents,
            )

        seen_refs: set[str] = set()
        for match in cls._IDENTIFIER_RE.finditer(content):
            ident = match.group(0)
            if ident not in cls._COMMON_STOPWORDS and ident not in seen_refs:
                seen_refs.add(ident)
                referenced_idents.append(ident)

        return ASTParseResult(
            symbols=symbols,
            imports=imports,
            defined_identifiers=defined_idents,
            referenced_identifiers=referenced_idents,
        )

    @classmethod
    def _fallback_python(
        cls,
        *,
        lines: list[str],
        line_byte_offsets: list[int],
        symbols: list[SymbolNode],
        imports: list[str],
        defined_idents: list[str],
    ) -> None:
        def_re = re.compile(
            r"^(?P<indent>[ \t]*)(?:async\s+)?(?P<kw>def|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
        )
        import_re = re.compile(r"^\s*(?:import|from)\s+[A-Za-z0-9_.]")

        total_lines = len(lines)
        class_stack: list[tuple[int, str]] = []

        for idx, line in enumerate(lines):
            if import_re.match(line):
                imports.append(line.strip())
                continue

            m = def_re.match(line)
            if not m:
                continue

            indent_len = len(m.group("indent").expandtabs(4))
            kw = m.group("kw")
            name = m.group("name")

            while class_stack and class_stack[-1][0] >= indent_len:
                class_stack.pop()

            parent_name = class_stack[-1][1] if class_stack else None
            kind = (
                SymbolKind.CLASS
                if kw == "class"
                else (SymbolKind.METHOD if parent_name else SymbolKind.FUNCTION)
            )
            qualified_name = f"{parent_name}.{name}" if parent_name else name
            defined_idents.append(name)

            if kw == "class":
                class_stack.append((indent_len, qualified_name))

            # Find end of Python signature (line ending with ':')
            sig_end_idx = idx
            while sig_end_idx < total_lines and not lines[sig_end_idx].rstrip().endswith(":"):
                sig_end_idx += 1
            if sig_end_idx >= total_lines:
                sig_end_idx = idx

            # Find end of indented block
            end_idx = sig_end_idx
            for look_idx in range(sig_end_idx + 1, total_lines):
                stripped = lines[look_idx].strip()
                if not stripped or stripped.startswith("#"):
                    continue
                cur_indent = len(lines[look_idx][: len(lines[look_idx]) - len(lines[look_idx].lstrip())].expandtabs(4))
                if cur_indent <= indent_len:
                    break
                end_idx = look_idx

            # Check for docstring right after signature
            docstring: str | None = None
            body_start_idx = sig_end_idx + 1
            if body_start_idx <= end_idx:
                first_stmt = lines[body_start_idx].strip()
                if first_stmt.startswith(('"""', "'''")):
                    quote_delim = first_stmt[:3]
                    doc_end_idx = body_start_idx
                    if first_stmt.count(quote_delim) < 2:
                        for d_idx in range(body_start_idx + 1, end_idx + 1):
                            doc_end_idx = d_idx
                            if quote_delim in lines[d_idx]:
                                break
                    docstring = "".join(lines[body_start_idx : doc_end_idx + 1]).strip()
                    body_start_idx = doc_end_idx + 1

            full_range = ByteRange(
                start_byte=line_byte_offsets[idx],
                end_byte=line_byte_offsets[end_idx + 1],
                start_line=idx + 1,
                end_line=end_idx + 1,
            )

            body_range: ByteRange | None = None
            if kind in {SymbolKind.FUNCTION, SymbolKind.METHOD} and body_start_idx <= end_idx:
                body_range = ByteRange(
                    start_byte=line_byte_offsets[body_start_idx],
                    end_byte=line_byte_offsets[end_idx + 1],
                    start_line=body_start_idx + 1,
                    end_line=end_idx + 1,
                )

            sig_text = "".join(lines[idx : sig_end_idx + 1]).strip().rstrip(":")
            symbols.append(
                SymbolNode(
                    name=name,
                    qualified_name=qualified_name,
                    kind=kind,
                    signature=sig_text,
                    docstring=docstring,
                    full_range=full_range,
                    body_range=body_range,
                    is_exported=not name.startswith("_"),
                    parent_symbol=parent_name,
                )
            )

    @classmethod
    def _fallback_c_family(
        cls,
        *,
        content: str,
        lines: list[str],
        line_byte_offsets: list[int],
        language_id: str,
        symbols: list[SymbolNode],
        imports: list[str],
        defined_idents: list[str],
    ) -> None:
        import_re = re.compile(r"^\s*(?:import\b|export\s+.*\bfrom\b|use\s+|#include\b|package\s+)")
        decl_re = re.compile(
            r"^(?P<indent>[ \t]*)(?:export\s+)?(?:default\s+)?(?:pub\s+)?(?:async\s+)?"
            r"(?P<kw>function|class|interface|struct|enum|fn|func)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
        )

        total_lines = len(lines)
        for idx, line in enumerate(lines):
            if import_re.match(line):
                imports.append(line.strip())
                continue

            m = decl_re.match(line)
            if not m:
                continue

            kw = m.group("kw")
            name = m.group("name")
            defined_idents.append(name)

            kind_map = {
                "class": SymbolKind.CLASS,
                "interface": SymbolKind.INTERFACE,
                "struct": SymbolKind.STRUCT,
                "enum": SymbolKind.ENUM,
                "function": SymbolKind.FUNCTION,
                "fn": SymbolKind.FUNCTION,
                "func": SymbolKind.FUNCTION,
            }
            kind = kind_map.get(kw, SymbolKind.FUNCTION)

            # Find matching closing brace across lines
            brace_balance = 0
            opened = False
            end_idx = idx
            body_open_byte: int | None = None
            body_open_line = idx + 1

            for look_idx in range(idx, total_lines):
                line_str = lines[look_idx]
                for char_idx, ch in enumerate(line_str):
                    if ch == "{":
                        if not opened:
                            opened = True
                            body_open_line = look_idx + 1
                            body_open_byte = line_byte_offsets[look_idx] + len(
                                line_str[:char_idx].encode("utf-8")
                            )
                        brace_balance += 1
                    elif ch == "}" and opened:
                        brace_balance -= 1
                        if brace_balance == 0:
                            end_idx = look_idx
                            break
                if opened and brace_balance == 0:
                    break

            full_range = ByteRange(
                start_byte=line_byte_offsets[idx],
                end_byte=line_byte_offsets[end_idx + 1],
                start_line=idx + 1,
                end_line=end_idx + 1,
            )

            body_range: ByteRange | None = None
            if (
                kind in {SymbolKind.FUNCTION, SymbolKind.METHOD}
                and opened
                and body_open_byte is not None
                and end_idx > idx
            ):
                body_end_byte = line_byte_offsets[end_idx + 1]
                body_range = ByteRange(
                    start_byte=body_open_byte,
                    end_byte=body_end_byte,
                    start_line=body_open_line,
                    end_line=end_idx + 1,
                )

            sig_text = line.strip().rstrip("{").strip()
            symbols.append(
                SymbolNode(
                    name=name,
                    qualified_name=name,
                    kind=kind,
                    signature=sig_text,
                    docstring=None,
                    full_range=full_range,
                    body_range=body_range,
                    is_exported=not name.startswith("_"),
                )
            )
