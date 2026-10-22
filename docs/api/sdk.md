# Compilation SDK

## ContextCraft

```{eval-rst}
.. autoclass:: contextcraft.ContextCraft
   :members: compile, analyze_repository
   :undoc-members:
```

Create a compiler with keyword options or a `CompilationConfig`. When `config`
is supplied, it is deep-copied and the constructor's other configuration
keywords are ignored. `registry` is independent of the configuration and is
used directly; omit it to create a fresh built-in registry.

```python
from contextcraft import ContextCraft, OutputFormat

compiler = ContextCraft(budget_tokens="16k", exclude_patterns=["tests/**"])
result = compiler.compile(".", focus_query="authentication", output_format=OutputFormat.XML)
print(result.content)
print(result.stats.compressed_tokens)
```

### compile

Scans the directory, redacts secrets if enabled, parses files, renders fidelity
tiers, ranks dependencies, selects tiers within the budget, and formats the
artifact. A Git checkout is not required.

Non-`None` per-call options override the stored configuration for that call
without mutating it. Lists replace rather than extend configured lists. Pass
`[]` to clear configured focus files or include/exclude patterns. Passing
`None` retains the configured value, including `focus_query`.

The return value is a [CompilationResult](models.md).
`content` contains the requested output format. The compatibility properties
`markdown` and `text_content` both return `content`, even for XML or JSON.

### analyze_repository

Returns ranked `FileAnalysis` objects with parsed ASTs and rendered tiers,
without budget optimization or artifact formatting. `selected_fidelity`
therefore remains `TREE`; read `tiers` explicitly to inspect richer content.
Secret redaction follows the compiler configuration and happens before parsing.

```python
from contextcraft import ContextCraft, FidelityLevel

for file in ContextCraft().analyze_repository("."):
    print(file.rel_path, file.pagerank_score)
    print(file.tiers[FidelityLevel.SIGNATURES].content)
    for symbol in file.symbols:
        print(file.parsed.text(symbol.signature_range))
```

## Configuration

```{eval-rst}
.. autoclass:: contextcraft.CompilationConfig
   :members: parse_budget
   :undoc-members:
```

Configuration is a Pydantic model. Unknown fields are rejected and assignments
are validated.

| Field                 | Default                 | Meaning                                                   |
| :-------------------- | :---------------------- | :-------------------------------------------------------- |
| `budget_tokens`       | `32000`                 | Positive token budget; accepts integer or shorthand input |
| `focus_query`         | `None`                  | Query used to boost relevant files                        |
| `focus_files`         | `[]`                    | Relative paths or globs to boost                          |
| `output_format`       | `OutputFormat.MARKDOWN` | Artifact format                                           |
| `include_patterns`    | `[]`                    | Include globs; empty means no include filter              |
| `exclude_patterns`    | `[]`                    | Additional exclude globs                                  |
| `respect_gitignore`   | `True`                  | Apply `.gitignore` and `.contextignore` rules             |
| `redact_secrets`      | `True`                  | Redact detected secrets before parsing                    |
| `max_file_size_bytes` | `1048576`               | Positive maximum file size                                |
| `tokenizer_encoding`  | `"cl100k_base"`         | tiktoken encoding name                                    |

`parse_budget()` accepts positive integers and decimal strings with optional
case-insensitive `k` (1,000) or `m` (1,000,000) suffixes. Outer whitespace and
whitespace before the suffix are accepted. Fractional tokens are truncated;
zero, negative values, booleans, and invalid formats raise `InvalidBudgetError`.

```python
from contextcraft import CompilationConfig, ContextCraft

config = CompilationConfig(budget_tokens="1.5k", focus_files=["src/**"])
assert config.budget_tokens == 1500
compiler = ContextCraft(config)
```

## Errors

All package-specific exceptions below inherit from `ContextCraftError`.
Validation errors from Pydantic and errors from external dependencies may also
propagate; they are not all wrapped in this hierarchy.

| Exception                 | Meaning                                                |
| :------------------------ | :----------------------------------------------------- |
| `ContextCraftError`       | Base package exception                                 |
| `RepositoryNotFoundError` | Repository path is missing or is not a directory       |
| `InvalidBudgetError`      | Unsupported budget type, format, or non-positive value |
| `ASTParseError`           | AST parsing error type                                 |
| `CompilationError`        | Compilation error type                                 |

These exceptions are importable directly from `contextcraft`. Parser errors
may instead be represented by `ParsedAst.has_errors`; do not assume every
syntax error raises `ASTParseError`.
