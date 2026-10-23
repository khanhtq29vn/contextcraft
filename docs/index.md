# ContextCraft

**AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Semantic Codebase Compressor for LLMs.**

`ContextCraft` compiles any Git repository into an optimal, high-signal Markdown, Claude XML, or JSON context artifact that strictly fits your target token budget (e.g., `4k`, `16k`, `32k`, `128k` tokens).

## Installation (PyPI & `uvx`)

```bash
# Run instantly without installing via uvx:
uvx contextcraft-ai . --budget 8k --focus "AST elision knapsack optimizer pagerank" -o context.md

# Or install globally / in your virtual environment from PyPI:
pip install contextcraft-ai
contextcraft . --budget 16k --format xml --copy
```

## Quickstart

```bash
# Compress the current repository into a strict 8,000-token budget
uv run contextcraft . --budget 8k --focus "authentication flow" --encoding o200k_base -o context.md
```

## Python SDK (Single-Pass & Reusable Snapshot)

```python
from contextcraft import ContextCraft, OutputFormat

cc = ContextCraft(focus_query="AST elision and knapsack optimizer")

# Single-call compilation:
result = cc.compile("./my-repo", budget_tokens="16k")
print(result.markdown)

# Or analyze once and render multiple budgets in milliseconds:
snapshot = cc.analyze("./my-repo")
small = snapshot.render(budget_tokens="4k")
large = snapshot.render(budget_tokens="32k", output_format=OutputFormat.XML)
```

```{toctree}
:maxdepth: 2
:caption: Contents

architecture
language-supports
api-reference
```
