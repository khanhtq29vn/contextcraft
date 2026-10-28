# ContextCraft

ContextCraft turns a repository into a smaller code context for an LLM by
ranking files according to their imports and relevance to your task, then
choosing how much of each file will fit within a token budget.

```bash
uvx --from 'contextcraft-ai[cli]' contextcraft . --budget 8000 -o context.md
```

This runs the CLI without a permanent installation.

Available as Markdown, XML, or JSON, the output combines full source,
declaration outlines, and a budgeted path listing. Python files receive
language-aware analysis, while other UTF-8 text files can still be included as
full source.

Start with [Getting started](getting-started.md) to compile your first
repository, or read the [current algorithm](concepts/algorithm.md) to
understand file selection and budget enforcement. Because token counting can
fall back to estimates, check the reported counting mode before treating a
budget as exact.

```{toctree}
:maxdepth: 1
:caption: Start here

getting-started
```

```{toctree}
:maxdepth: 1
:caption: Guides

guides/cli
guides/python-sdk
guides/adding-a-language
guides/languages
```

```{toctree}
:maxdepth: 1
:caption: Concepts

concepts/pipeline
concepts/algorithm
concepts/algorithm-old
```

```{toctree}
:maxdepth: 1
:caption: Reference

reference/cli
reference/configuration
reference/api/compiler
reference/api/stages
reference/api/models
reference/api/language
```

```{toctree}
:maxdepth: 1
:caption: Contributing

contributing/adding-a-language
```
