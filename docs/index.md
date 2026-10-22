# ContextCraft

**AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Semantic Codebase Compressor for LLMs.**

`ContextCraft` compiles any Git repository into an optimal, high-signal Markdown, Claude XML, or JSON context artifact that strictly fits your target token budget (e.g., `4k`, `16k`, `32k`, `128k` tokens).

## Installation (PyPI & `uvx`)

```bash
# Run instantly without installing via uvx:
uvx contextcraft-ai . --budget 16k --focus "AST elision and knapsack optimizer" -o context.md

# Or install globally / in your virtual environment from PyPI:
pip install contextcraft-ai
contextcraft . --budget 32k --format xml --copy
```

## Quickstart

```bash
# Compress the current repository into a strict 16,000-token budget
uv run contextcraft . --budget 16k --focus "authentication flow" -o context.md
```

## Python SDK (3 Lines of Code)

```python
from contextcraft import ContextCraft

cc = ContextCraft(budget_tokens="32k")
result = cc.compile("./my-repo", focus_query="AST elision and knapsack optimizer")
print(result.markdown)
```

```{toctree}
:maxdepth: 2
:caption: Contents

architecture
language-supports
api-reference
```
