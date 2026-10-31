# ContextCraft

<div align="center">

**AST-Aware, Personalized-PageRank-Ranked, Token-Budgeted Codebase Compressor for LLMs**

[![CI](https://github.com/khanhtq29vn/contextcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/khanhtq29vn/contextcraft/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/contextcraft-ai.svg)](https://pypi.org/project/contextcraft-ai/)
[![Rust](https://img.shields.io/badge/core-Rust-orange.svg)](crates/contextcraft_core)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

ContextCraft turns a repository into code context that fits an LLM's token
budget. It ranks files by their dependencies and relevance to your task, then
chooses between full source, AST-based outlines, and paths to decide how much
of each file to include.

- 🦀 A Rust core handles parsing, ranking, token counting, and budget allocation. Python bindings expose the pipeline through the SDK and CLI, releasing the GIL during analysis.
- 🔎 Personalized PageRank and BM25F query matching favor relevant files and their dependencies.
- 🎚️ Four fidelity tiers balance source detail against token cost instead of truncating files at an arbitrary boundary.
- 📄 Markdown, XML, and JSON output work with the CLI or your own Python application.
- 🛡️ Git ignore rules, exclude patterns, and secret redaction control what enters the artifact before analysis.

[Documentation](https://khanhtq29vn.github.io/contextcraft/) ·
[Getting started](docs/src/content/docs/getting-started/quickstart.md) ·
[Python SDK](docs/src/content/docs/python/quickstart.md)

## Quick start

Run with [uv](https://docs.astral.sh/uv/) without a permanent installation:

```bash
uvx --from 'contextcraft-ai[cli]' contextcraft . --budget 8000 --focus "authentication" -o context.md
```

This writes a Markdown artifact to `context.md` and prints a summary to stderr,
including the output token count and selected tiers. Budgets accept integers
such as `8000` or shorthand such as `8k`.

For regular use, install the CLI as a tool and choose the format and tokenizer
that suit your workflow:

```bash
uv tool install 'contextcraft-ai[cli]'
contextcraft . --budget 16000 --format xml --encoding o200k_base -o context.xml
```

Use `--focus-file 'src/auth/**'` to prefer a subsystem, or repeat `--exclude`
to leave files out of the scan. Focus changes rankings without guaranteeing a
particular file tier. See the [focus guide](docs/src/content/docs/guides/focus.md)
for examples and the [CLI reference](docs/src/content/docs/reference/cli.md)
for all options.

## Use it from Python

Add the SDK to your application:

```bash
uv add contextcraft-ai
```

Create a pipeline with the budget, focus query, and output format you need:

```python
from contextcraft import Config, ContextCraft, OutputFormat

compiler = ContextCraft(
    Config(
        budget_tokens=8000,
        focus_query="authentication",
        output_format=OutputFormat.JSON,
    )
)
analysis = compiler.run(".")
artifact = analysis.artifact

print(artifact.content)
print(artifact.tokens, artifact.token_counts_estimated)
```

The SDK returns the artifact and intermediate pipeline data without writing a
file. Each call reads and analyzes the repository again. Source analysis and
tier rendering run in parallel by default; set `Config(enable_parallel=False)`
for sequential execution. Follow the [SDK guide](docs/src/content/docs/python/quickstart.md)
for configuration and intermediate results.

## What goes into the context?

The allocator weighs each file's rank against the cost of its available tiers,
then the formatter checks the complete output and lowers fidelity if needed.

| Tier   | Content                                                         |
| :----- | :-------------------------------------------------------------- |
| `FULL` | Complete loaded source after optional redaction                 |
| `SKEL` | An outline with retained structure and documentation            |
| `SIGS` | A compact declaration outline                                   |
| `TREE` | No file content, with a path entry if the listing budget allows |

Outline content depends on the language implementation and does not need to be
executable source. Files without a matching implementation can still be loaded
as UTF-8 text, with their compressed tiers reusing the full source. Read
[how compression works](docs/src/content/docs/reference/architecture.md) for
ranking and allocation details.

The Rust tokenizer counts the complete serialized artifact, including paths
and output framing. Final counts are exact; the current implementation does
not fall back to estimates. A budget too small for the output framing returns
an error.

Review the artifact before sharing it, because enabled secret redaction does
not guarantee that every credential is detected.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

[MIT](LICENSE).
