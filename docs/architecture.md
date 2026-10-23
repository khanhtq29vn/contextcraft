# Architecture & Mathematical Formulation

`ContextCraft` replaces naive alphabetical file concatenation with a 5-stage compiler pipeline:

1. **Gitignore-Aware Ingestion & Pre-AST Secret Sanitization:**
   Scrubs API keys, PEM blocks, and high-entropy credentials before parsing, preserving line endings and string quotes. AST byte offsets refer to the sanitized source.
2. **Language Registry & Tree-sitter AST Parsing:**
   Detects languages through `LanguageSpec` extensions and filenames. Each language package defines its language metadata, extractor, skeleton builder, and signatures builder. Extractors produce a byte-backed `ParsedAst` with symbols, imports, lexical scopes, and source ranges. Missing grammars preserve the source; builders also preserve source with syntax errors.
   HTML stores inline JavaScript and CSS as embedded AST regions. Its skeleton builder reuses their language builders and applies all replacements in reverse byte order. Unsupported script types and external scripts remain unchanged.
3. **Cross-File Dependency Graph & Personalized PageRank:**
   Constructs a weighted directed multigraph $G = (V, E)$ from module imports and symbol references. Computes centrality $w_i = \text{PageRank}(i; q)$ biased toward `--focus` query matches via BM25 lexical scoring and 1-hop neighbor diffusion.
4. **Multi-Resolution AST Elision:**
   Pre-computes 4 discrete representations $l \in \{0, 1, 2, 3\}$ for each file $i$:

   - $l = 3$ (`FULL`): Complete sanitized source code ($u(3) = 1.00$).
   - $l = 2$ (`SKEL`): Surgical AST body elision preserving imports, signatures, type annotations, and docstrings ($u(2) = 0.82$).
   - $l = 1$ (`SIGS`): Public signatures and imports only ($u(1) = 0.45$).
   - $l = 0$ (`TREE`): Directory tree entry only ($u(0) = 0.00$).

5. **Budget Allocation (MCKP Heuristic):**
   Selects one fidelity tier $l_i \in \{0, 1, 2, 3\}$ per file using marginal utility per token and local refinement. Let $r_i(l)$ be the number of named public code declarations whose signatures are actually retained at tier $l$. The objective rewards API breadth as well as implementation fidelity:

$$\max_{\{l_i\}} \sum_{i=1}^{N} w_i \cdot \bigl(r_i(l_i) + u(l_i)\bigr) \quad \text{s.t.} \quad \text{Overhead}_{\text{tree}} + \sum_{i=1}^{N} C_{\text{eff}}(i, l_i) \le B$$

Individual signature additions compete with whole-file upgrades by the same marginal utility per token. A selected method includes its enclosing type, and partial signature output is syntax-checked and marked explicitly. Signature builders share import trimming: known named bindings used only by omitted implementations are removed, while imports needed by declarations, annotations, defaults, decorators, or module-level re-exports remain. Side-effect loads, wildcard imports, and imports whose bindings cannot be determined safely are preserved. Original ASTs and full-source tiers remain unchanged.

The directory tree uses at most 10% of the token budget. If the full tree does not fit, a compact list prioritizes highly ranked paths and reports omitted files. After formatting, the emitted artifact is counted again; if necessary, tiers are downgraded by the least utility lost per estimated token saved until the output fits.
