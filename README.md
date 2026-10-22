# ContextCraft

<div align="center">

**AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Semantic Codebase Compressor for LLMs**

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/contextcraft/contextcraft/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/contextcraft.svg)](https://pypi.org/project/contextcraft-ai/)
[![Typed: mypy strict](https://img.shields.io/badge/typing-mypy%20--strict-indigo.svg)](https://mypy-lang.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Why ContextCraft?

Existing repository packers (`repomix`, `gitingest`, `code2prompt`) blindly concatenate every file verbatim. On real-world repositories, this blows past LLM context budgets, buries critical architecture inside thousands of lines of boilerplate (*Lost-in-the-Middle* degradation), and wastes API tokens.

**`ContextCraft` is the AST-aware "MarkItDown for Codebases."** Instead of naive concatenation or arbitrary character truncation, `ContextCraft` parses your codebase with **Tree-sitter**, ranks every file's architectural importance via **Personalized PageRank** on the cross-file dependency graph, and solves a **Multiple-Choice Knapsack Problem (MCKP)** across 4 AST fidelity tiers (`FULL`, `SKEL`, `SIGS`, `TREE`) to pack maximum architectural signal into your exact token budget $B$.

---

## 10-Second Quickstart

### 1. Installation (PyPI & `uvx`)

```bash
# Run instantly without installing via uvx:
uvx contextcraft-ai . --budget 16k --focus "AST elision and knapsack optimizer" -o context.md

# Or install globally / in your virtual environment from PyPI:
pip install contextcraft-ai
contextcraft . --budget 32k --format xml --copy
```

### 2. Command-Line Interface (CLI)

```bash
# Compress a repository into a strict 4,000-token budget biased toward your task
uv run contextcraft . --budget 4k --focus "AST elision and knapsack optimizer" -o context.md

# Emit Anthropic Claude-optimized <repository_context> XML and copy to clipboard
uv run contextcraft . --budget 32k --format xml --copy
```

### 3. Python SDK (Modeled after `microsoft/markitdown`)

```python
from contextcraft import ContextCraft

cc = ContextCraft(budget_tokens="16k")
result = cc.compile("./my-repo", focus_query="authentication middleware")

print(result.markdown)
print(
    f"Compression: {result.stats.compression_ratio}x ({result.stats.compressed_tokens} / {result.stats.budget_tokens} tokens)"
)
```

### 4. Interactive Web Playground & "URL Swap Trick"

```bash
uv run uvicorn web.app:app --reload --port 8000
```

Open `http://127.0.0.1:8000` to interactively tune token budgets, inspect PageRank scores, or use the **URL Swap Trick**: visit `http://127.0.0.1:8000/<owner>/<repo>?budget=32k&focus=auth` to automatically clone and compress any public GitHub repository!

---

## Architecture Pipeline

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. RepositoryScanner & SecretSanitizer                                     │
│    • Hierarchical .gitignore / .contextignore & binary filtering           │
│    • Pre-AST API key, PEM & high-entropy secret scrubbing (line-preserving)│
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 2. UniversalASTParser (Tree-sitter + Deterministic Fallback)               │
│    • Extracts classes, functions, methods, signatures, and docstrings      │
│    • Computes exact post-docstring `body_range` spans for surgical elision │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 3. DependencyGraphScorer (Cross-File MultiDiGraph + Personalized PageRank) │
│    • Weighted edges from module imports & IDF-scaled symbol references     │
│    • BM25 query personalization (--focus) + 1-hop neighbor diffusion       │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 4. MultiResolutionElider (4 Discrete AST Fidelity Tiers per File)          │
│    • Tier 3 [FULL] (u=1.00): Complete sanitized source code                │
│    • Tier 2 [SKEL] (u=0.82): Signatures + types + docstrings (body elided) │
│    • Tier 1 [SIGS] (u=0.45): Imports & public declarations only            │
│    • Tier 0 [TREE] (u=0.00): Annotated directory tree entry only           │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 5. TokenBudgetOptimizer (Multiple-Choice Knapsack Solver) & Formatter      │
│    • Maximizes ∑ PageRank(i) · u(l_i) subject to TotalTokens ≤ Budget B    │
│    • Emits Markdown, Claude XML, or JSON with strict budget verification   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Quantitative Benchmark (`ContextCraft` Repository)

Evaluated using `benchmarks/run_benchmark.py` (`--focus "AST elision knapsack optimizer pagerank"`):

- **Raw Uncompressed Repository (`repomix` / verbatim concatenation baseline):** `43,151` tokens (`1.00x`)

| Method | Target Budget ($B$) | Emitted Tokens | Compression Ratio | Public API Signature Coverage | Budget Compliant |
| :--- | ---: | ---: | ---: | ---: | :---: |
| **Naive Prefix Truncation** | `4,000` | `4,000` | `10.79x` | `18.4%` | YES (Loses 81% of repo) |
| **ContextCraft (Ours)** | `4,000` | `3,950` | **`10.92x`** | **`70.9%`** | **YES (`98.8%` utilization)** |
| **Naive Prefix Truncation** | `6,000` | `6,000` | `7.19x` | `31.6%` | YES (Loses 68% of repo) |
| **ContextCraft (Ours)** | `6,000` | `5,940` | **`7.26x`** | **`94.3%`** | **YES (`99.0%` utilization)** |

---

## Development & Verification

```bash
# Install all dependencies (core, web, and dev)
uv sync --locked --all-extras --dev

# Run lint, strict type checking, and test coverage
uv run ruff check src tests web benchmarks
uv run mypy src/contextcraft
uv run pytest --cov=contextcraft --cov-report=term-missing
```

## License

Released under the [MIT License](LICENSE).
