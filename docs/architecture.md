# Architecture & Mathematical Formulation

`ContextCraft` replaces naive alphabetical file concatenation with a 5-stage compiler pipeline:

1. **Gitignore-Aware Ingestion & Pre-AST Secret Sanitization (`scanner.py`, `sanitizer.py`):**
   Scrubs API keys, PEM blocks, and high-entropy credentials before parsing, preserving line endings and string quotes. AST byte offsets refer to the sanitized source.
2. **Language Registry & Tree-sitter AST Parsing (`ast/parser.py`, `languages/`):**
   Detects languages through `LanguageSpec` extensions and filenames. Each language package defines `language.py`, `extraction.py`, `skeleton.py`, and `signatures.py`. Extractors produce a byte-backed `ParsedAst` with symbols, imports, lexical scopes, and source ranges. Missing grammars preserve the source; builders also preserve source with syntax errors.
   HTML stores inline JavaScript and CSS as embedded AST regions. Its skeleton builder reuses their language builders and applies all replacements in reverse byte order. Unsupported script types and external scripts remain unchanged.
3. **Cross-File Dependency Graph & Personalized PageRank (`graph.py`):**
   Constructs a weighted directed multigraph $G = (V, E)$ from module imports and symbol references. Computes centrality $w_i = \text{PageRank}(i; q)$ biased toward `--focus` query matches via BM25 lexical scoring and 1-hop neighbor diffusion.
4. **Multi-Resolution AST Elision (`elider.py`):**
    Pre-computes 4 discrete representations $l \in \{0, 1, 2, 3\}$ for each file $i$:

    - $l = 3$ (`FULL`): Complete sanitized source code ($u(3) = 1.00$).
    - $l = 2$ (`SKEL`): Surgical AST body elision preserving imports, signatures, type annotations, and docstrings ($u(2) = 0.82$).
    - $l = 1$ (`SIGS`): Public signatures and imports only ($u(1) = 0.45$).
    - $l = 0$ (`TREE`): Directory tree entry only ($u(0) = 0.00$).

5. **Multiple-Choice Knapsack Problem (MCKP) Solver (`optimizer.py`):**
   Selects exactly one fidelity tier $l_i \in \{0, 1, 2, 3\}$ per file to maximize total architectural utility under strict token budget $B$:

$$\max_{\{l_i\}} \sum_{i=1}^{N} w_i \cdot u(l_i) \quad \text{s.t.} \quad \text{Overhead}_{\text{tree}} + \sum_{i=1}^{N} C_{\text{eff}}(i, l_i) \le B$$