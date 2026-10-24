# Architecture & Mathematical Formulation

`ContextCraft` replaces naive alphabetical file concatenation with a 5-stage compiler pipeline:

1. **Gitignore-Aware Ingestion & Pre-AST Secret Sanitization:**
   Scrubs API keys, PEM blocks, and high-entropy credentials before parsing, preserving line endings and string quotes. AST byte offsets refer to the sanitized source.
2. **Language Registry & Tree-sitter AST Parsing:**
   Detects languages through `LanguageSpec` extensions and filenames. Each language package defines its language metadata, extractor, skeleton builder, and signatures builder. Extractors produce a byte-backed `ParsedAst` with symbols, imports, lexical scopes, and source ranges. Missing grammars preserve the source; builders also preserve source with syntax errors.
   HTML stores inline JavaScript and CSS as embedded AST regions. Its skeleton builder reuses their language builders and applies all replacements in reverse byte order. Unsupported script types and external scripts remain unchanged.
3. **Cross-File Dependency Graph, BM25F & Personalized PageRank (`contextcraft/graph.py`):**
   Constructs a weighted directed multigraph $G = (V, E)$ from module imports and scope-resolved cross-file symbol references. Computes centrality $w_i = \text{PageRank}(i; q)$ via pure-Python power iteration biased toward `--focus` query matches using field-normalized **BM25F** ($k_1 = 1.2, b = 0.75$), 1-hop neighbor diffusion, and automatic dampening ($0.02\times$) for unfocused test/benchmark files.
4. **Multi-Resolution AST Elision (`contextcraft/elider.py`):**
   Pre-computes 4 discrete representations $l \in \{0, 1, 2, 3\}$ for each file $i$ in reverse byte order:
   - $l = 3$ (`FULL`): Complete sanitized source code ($u(3) = 1.00$).
   - $l = 2$ (`SKEL`): Surgical AST body elision preserving imports, signatures, type annotations, and docstrings ($u(2) = 0.82$).
   - $l = 1$ (`SIGS`): Public signatures and grammar-trimmed imports or structural outline ($u(1) = 0.45$).
   - $l = 0$ (`TREE`): Directory tree entry only ($u(0) = 0.00$), with directory tree overhead capped at $\le 10\%$ of total budget $B$.
5. **Multiple-Choice Knapsack Problem (MCKP) Solver (`contextcraft/optimizer.py`, `contextcraft/formatter.py`):**
   Selects exactly one fidelity tier $l_i \in \{0, 1, 2, 3\}$ per file to maximize total architectural utility under strict token budget $B$:

$$\max_{\{l_i\}} \sum_{i=1}^{N} w_i \cdot v_i(l_i) \quad \text{s.t.} \quad \text{Overhead}_{\text{tree}} + \sum_{i=1}^{N} C_{\text{eff}}(i, l_i) \le B$$

$$v_i(l) = m_i \cdot \min\big(u(l), u(2)\big) + \max\big(0, u(l) - u(2)\big), \qquad m_i = T_i^{1/3}$$

   where $T_i$ is the token count of file $i$ at `FULL` fidelity. Declarations (`SIGS`, `SKEL`) are scaled by the content mass $m_i$, because a large file exposes more structure than a tiny one: without it, a 60-token config file at `FULL` scored as high as a 12,000-token core module at `FULL`, so the solver dropped central files entirely to fund dozens of trivial ones. The cube root keeps that growth sublinear: a file 1,000× larger is worth 10× more at the same rank, so it can outrank a file with up to 10× its PageRank. The function bodies that `FULL` adds keep their size-blind value $u(3) - u(2)$.

## Marginal Utility Density & "God Object" Immunity

To prevent oversized hub files ("God Objects") from monopolizing the token budget at `FULL` fidelity, `TokenBudgetOptimizer` prioritizes upgrades using a min-heap ordered by **marginal utility density**:

$$\rho(i, l \to l') = \frac{w_i \cdot \big(v_i(l') - v_i(l)\big)}{C_{\text{eff}}(i, l') - C_{\text{eff}}(i, l)}$$

The greedy pass is followed by a prefix-indexed binary-search swap refinement pass (`bisect_right`) in $O(N \log N)$ time and $O(N)$ memory, and a post-render budget verification pass in `ArtifactFormatter` that trims the cheapest utility per token first.

Because the `SKEL` $\to$ `FULL` increment is not scaled by $m_i$, a giant file's body upgrade has the same low density as before the content mass was introduced, while its neighbours' declaration upgrades are scaled up. The giant file therefore stays at `SKEL` until its neighbours' denser upgrades are funded.
