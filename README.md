# ContextCraft

<div align="center">

**AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Semantic Codebase Compressor for LLMs**

[![CI](https://github.com/khanhtq29vn/contextcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/khanhtq29vn/contextcraft/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/contextcraft-ai.svg)](https://pypi.org/project/contextcraft-ai/)
[![Typed: mypy strict](https://img.shields.io/badge/typing-mypy%20--strict-indigo.svg)](https://mypy-lang.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Why ContextCraft?

Existing repository packers (`repomix`, `gitingest`, `code2prompt`) blindly concatenate every file verbatim in alphabetical order. On real-world repositories, this blows past local and cloud LLM context budgets, buries critical interfaces inside thousands of lines of implementation boilerplate (_Lost-in-the-Middle_ degradation), or—when truncated—drops 70–85% of the repository's architecture.

**`ContextCraft` is the AST-aware "MarkItDown for Codebases"**. Instead of naive concatenation or arbitrary character truncation, `ContextCraft` parses **35 languages and formats** with **Tree-sitter**, resolves cross-file lexical scopes and imports to rank architectural centrality via **Personalized PageRank + BM25F**, and solves a **Multiple-Choice Knapsack Problem (MCKP)** across 4 AST fidelity tiers (`FULL`, `SKEL`, `SIGS`, `TREE`) to pack maximum architectural signal into your exact token budget $B$.

---

## 10-Second Quickstart

### 1. Installation (PyPI & `uvx`)

```bash
# Run instantly without installing via uvx:
uvx contextcraft-ai . --budget 8k --focus "AST elision knapsack optimizer pagerank" -o context.md

# Or install globally / in your virtual environment from PyPI:
pip install contextcraft-ai
contextcraft . --budget 16k --format xml --copy
```

### 2. Command-Line Interface (CLI)

```bash
# Compress a repository into a strict 8,000-token budget biased toward your task
uv run contextcraft . --budget 8k --focus "AST elision knapsack optimizer pagerank" -o context.md

# Emit Anthropic Claude-optimized <repository_context> XML and copy to clipboard
uv run contextcraft . --budget 16k --format xml --copy

# Account tokens with GPT-4o / o3 o200k_base encoding (default is cl100k_base)
uv run contextcraft . --budget 8k --encoding o200k_base -o context.md
```

### 3. Python SDK (Single-Pass Compilation & Reusable Snapshots)

```python
from contextcraft import ContextCraft, OutputFormat

cc = ContextCraft(focus_query="AST elision and knapsack optimizer", tokenizer_encoding="o200k_base")

# Analyze once (scan, sanitize, parse Tree-sitter ASTs, and compute PageRank):
snapshot = cc.analyze(".")

# Render multiple token budgets or formats in milliseconds without reparsing:
res_8k = snapshot.render(budget_tokens="8k", output_format=OutputFormat.MARKDOWN)
res_16k = snapshot.render(budget_tokens="16k", output_format=OutputFormat.XML)

print(
    f"Compression: {res_8k.stats.compression_ratio}x "
    f"({res_8k.stats.compressed_tokens} / {res_8k.stats.budget_tokens} tokens)"
)
```

### 4. Interactive Web Playground & "URL Swap Trick"

```bash
uv run uvicorn web.app:app --reload --port 8000
```

Open `http://127.0.0.1:8000` to interactively tune token budgets, inspect PageRank scores, or use the **URL Swap Trick**: visit `http://127.0.0.1:8000/<owner>/<repo>?budget=16k&focus=auth` to automatically clone and compress any public GitHub repository.

Local repository paths must stay inside the server's working directory by default. To serve repositories from another directory, set `CONTEXTCRAFT_WEB_ROOT` before starting the server:

```bash
CONTEXTCRAFT_WEB_ROOT="$HOME/repositories" uv run uvicorn web.app:app --host 127.0.0.1 --port 8000
```

---

## Architecture Pipeline (`v0.3.0`)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. RepositoryScanner & SecretSanitizer                                     │
│    • Hierarchical .gitignore / .contextignore, >1 MiB & binary filtering   │
│    • Pre-AST API key, PEM & high-entropy secret scrubbing (line-preserving)│
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 2. 35-Language Registry, Tree-sitter Scope Graph & ImportTrimmer           │
│    • Byte-backed ParsedAst with symbols, docstrings & lexical ScopeGraph   │
│    • Trims unused implementation imports in SIGS mode across 10+ languages │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 3. DependencyGraphScorer (Cross-File MultiDiGraph + PageRank + BM25F)      │
│    • Scope-resolved symbol reference edges + module import edges           │
│    • Field-normalized BM25F (--focus), 1-hop diffusion & test dampening    │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 4. Elider & Per-Language Builders (4 Monotonic AST Fidelity Tiers)         │
│    • Tier 3 [FULL] (u=1.00): Complete sanitized source code                │
│    • Tier 2 [SKEL] (u=0.82): Signatures + types + docstrings (body elided) │
│    • Tier 1 [SIGS] (u=0.45): Public declarations & trimmed imports only    │
│    • Tier 0 [TREE] (u=0.00): Budget-capped directory tree entry (<=10%)    │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 5. TokenBudgetOptimizer (O(N log N) Heap + Prefix Swap MCKP Solver)        │
│    • Declarations weighted by (FULL tokens)^(1/3): hubs outrank trivia     │
│    • Marginal utility density (ΔUtility / ΔTokens) prevents "God Objects"  │
│      from hogging FULL budget; verified by ArtifactFormatter post-check    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Reproducible Benchmark (`ContextCraft v0.3.1` Repository — `258` Files, `138,468` Raw Tokens)

Reproduce these exact telemetry numbers on the repository root:

```bash
uv run contextcraft . --budget 8k --focus "AST elision knapsack optimizer pagerank" -o /tmp/context_8k.md
uv run contextcraft . --budget 12k --focus "AST elision knapsack optimizer pagerank" -o /tmp/context_12k.md
uv run python benchmarks/run_benchmark.py . --budgets 4000,6000,8000,12000,16000
```

| Target Budget (`B`)             | Emitted Tokens | Budget Utilization | Compression Ratio | Tokens Saved | Fidelity Allocation (`FULL / SKEL / SIGS / TREE`)                              |
| :------------------------------ | -------------: | -----------------: | ----------------: | -----------: | :----------------------------------------------------------------------------- |
| **Uncompressed (`repomix`)**    |      `138,468` |   Overflow (`17x`) |           `1.00x` |       `0.0%` | `258 FULL`                                                                     |
| **ContextCraft `--budget 4k`**  |        `3,966` |            `99.2%` |      **`34.91x`** |  **`97.1%`** | `0 FULL \| 5 SKEL \| 10 SIGS \| 243 TREE`                                      |
| **ContextCraft `--budget 8k`**  |        `7,985` |            `99.8%` |      **`17.34x`** |  **`94.2%`** | `0 FULL \| 19 SKEL \| 10 SIGS \| 229 TREE`                                     |
| **ContextCraft `--budget 12k`** |       `11,990` |            `99.9%` |      **`11.55x`** |  **`91.3%`** | `2 FULL \| 24 SKEL \| 11 SIGS \| 221 TREE`                                     |
| **ContextCraft `--budget 16k`** |       `15,967` |            `99.8%` |       **`8.67x`** |  **`88.5%`** | Core Symbol Retention (`44.2%`) & API Coverage (`33.0%`) beat Naive Truncation |

---

## Enterprise & Legacy Codebase Best Practices

When applying `ContextCraft` to large, long-lived enterprise repositories:

1. **Built-in "God Object" Protection:** `TokenBudgetOptimizer` weights a file's declarations (`SIGS`, `SKEL`) by PageRank × its content mass ($T^{1/3}$, where $T$ is its `FULL` token count) and allocates tiers by **marginal utility density** ($\rho = \Delta \text{Utility} / \Delta \text{Tokens}$); `DependencyGraphScorer` normalizes document lengths via **BM25F** ($b = 0.75$). The content mass keeps large central files from being dropped in favor of tiny peripheral ones, while the function bodies that `FULL` adds stay size-blind: if a legacy codebase contains a massive 10,000-token "God Class" with high PageRank, upgrading it from `SKEL` ($u = 0.82$) to `FULL` ($u = 1.00$) still has a very low density $\rho$ due to the huge $\Delta \text{Tokens}$ denominator. The solver automatically keeps the God Class at `SKEL` (preserving its interface and docstrings) while saving thousands of tokens to keep surrounding business-logic modules at `FULL`.
2. **Scope Chaining for Targeted Debugging:** For surgical bug hunting in a specific subsystem of a massive monorepo, combine `--include` / `--exclude` (or `.contextignore`) with `--focus-file`:
   ```bash
   contextcraft . --include "contextcraft/languages/**" --focus-file "contextcraft/languages/structural.py" --budget 12k
   ```
3. **Pin What You Are Debugging:** When a legacy file must be seen verbatim, `--pin-full` (repeatable; the same gitignore-style patterns as `--include`) keeps it at `FULL` and lets the solver budget the rest around it:
   ```bash
   contextcraft . --pin-full "src/billing/legacy_invoice.py" --focus "invoice rounding" --budget 16k
   ```
4. **100% Offline Local LLM Workflows:** While `SecretSanitizer` automatically scrubs API keys, PEM blocks, and high-entropy secrets, proprietary business logic should never be sent to unapproved public cloud APIs. Pair `ContextCraft`'s `--budget 8k` or `16k` output directly with local models (`Qwen-2.5-Coder`, `Llama-3.3`, `DeepSeek`) running on internal GPUs via Ollama, vLLM, or `llama.cpp`.

---

## Development & Verification

```bash
# Install all dependencies (core, web, and dev)
uv sync --locked --all-extras --dev

# Run lint, strict type checking (217 source files), and test suite (492 tests, 94% coverage)
uv run ruff check contextcraft tests web benchmarks
uv run mypy contextcraft
uv run pytest --cov=contextcraft --cov-report=term-missing
```

## License

Released under the [MIT License](LICENSE).
