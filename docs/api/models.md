# Results and AST Models

Unless a module path is shown, the types on this page can be imported directly
from `contextcraft`.

## Compilation results

```{eval-rst}
.. autoclass:: contextcraft.CompilationResult
   :members: markdown, text_content
   :undoc-members:
```

| Field           | Meaning                                                     |
| :-------------- | :---------------------------------------------------------- |
| `root_path`     | Resolved repository root as a string                        |
| `output_format` | Selected `OutputFormat`                                     |
| `content`       | Complete formatted artifact                                 |
| `stats`         | `CompilationStats` for this compilation                     |
| `files`         | Analyzed files, including files selected at `TREE` fidelity |

`markdown` and `text_content` are aliases for `content`, not format converters.

```{eval-rst}
.. autoclass:: contextcraft.OutputFormat
   :members:
   :undoc-members:
```

## Statistics

`CompilationStats` is a Pydantic model with the following fields. Use
`result.stats.model_dump()` for a dictionary or `model_dump_json()` for JSON.

| Field                      | Meaning                                                        |
| :------------------------- | :------------------------------------------------------------- |
| `total_files_discovered`   | Files discovered during scanning                               |
| `binary_files_skipped`     | Files skipped as binary                                        |
| `ignored_files_skipped`    | Files skipped by filtering or scan constraints                 |
| `files_compiled`           | Number of analyzed files, including `TREE` selections          |
| `raw_tokens`               | Sum of the analyzed files' `FULL` tier token counts            |
| `compressed_tokens`        | Token count of the complete formatted artifact                 |
| `tree_overhead_tokens`     | Token count of the directory tree                              |
| `budget_tokens`            | Requested token budget                                         |
| `budget_utilization_pct`   | Artifact tokens divided by budget, times 100                   |
| `compression_ratio`        | Raw tokens divided by artifact tokens (1.0 if no raw tokens)   |
| `token_savings_pct`        | Percentage reduction from raw tokens to artifact tokens        |
| `fidelity_counts`          | File counts by fidelity badge (`TREE`, `SIGS`, `SKEL`, `FULL`) |
| `total_symbols_extracted`  | Number of extracted symbols                                    |
| `preserved_signatures_pct` | Percentage of symbol signatures retained in selected content   |
| `secrets_redacted`         | Number of detected secrets redacted                            |
| `execution_time_ms`        | Compilation duration in milliseconds                           |

Raw tokens are counted after redaction. Artifact counts include formatting
overhead, so token savings can be negative for small inputs.

## File analysis

```{eval-rst}
.. autoclass:: contextcraft.FileAnalysis
   :members: symbols, imports, defined_identifiers, referenced_identifiers, raw_tokens, tier_tokens, selected_content, selected_tokens, redacted_secrets_count
   :undoc-members:
```

`parsed` holds the byte-backed AST. `tiers` maps `FidelityLevel` to
`RenderedTier`. `pagerank_score` and `relevance_boost` describe ranking;
`selected_fidelity` identifies the tier chosen for output. `imports` returns
import declaration text, while `parsed.imports` contains structured `Import`
objects. `redacted_secrets` contains `SecretMatch` records.

## Fidelity and token counting

```{eval-rst}
.. autoclass:: contextcraft.FidelityLevel
   :members:
   :undoc-members:
```

| Level        | Value | Content                                                |
| :----------- | :---- | :----------------------------------------------------- |
| `TREE`       | `0`   | Empty file content; path remains in the directory tree |
| `SIGNATURES` | `1`   | Language-specific signatures or compact summary        |
| `SKELETON`   | `2`   | Structural representation with implementation elided   |
| `FULL`       | `3`   | Full source after optional redaction                   |

```{eval-rst}
.. autoclass:: contextcraft.RenderedTier
```

`content` is the rendered text and `tokens` is its token count.

```{eval-rst}
.. autoclass:: contextcraft.TokenCounter
   :members: count
   :undoc-members:
```

Uses the requested tiktoken encoding. An unknown encoding raises `ValueError`.
If tokenization is unavailable or fails, counting falls back to a lexical/byte
estimate.

```{eval-rst}
.. autoclass:: contextcraft.Elider
   :members: render
   :undoc-members:
```

`render()` produces all four tiers. Empty compressed output or a compressed
tier larger than the next richer tier falls back to that richer tier. A custom
counter only needs a `count(text: str) -> int` method, as specified by
`contextcraft.elider.TokenCounterProtocol`.

## AST data

All ranges are half-open UTF-8 **byte offsets**, not character indexes. Use
`ParsedAst.text()` rather than slicing a decoded Python string with them.
When redaction is enabled, ranges refer to the sanitized source.

```{eval-rst}
.. autoclass:: contextcraft.ByteRange
```

```{eval-rst}
.. autoclass:: contextcraft.Symbol
   :members: qualified_name
   :undoc-members:
```

A symbol describes its declaration, signature, optional body and docstring,
parent, and public visibility. `qualified_name` joins named parents with dots;
it is `None` for unnamed symbols.

```{eval-rst}
.. autoclass:: contextcraft.Import
```

```{eval-rst}
.. autoclass:: contextcraft.ParsedAst
   :members: text, defined_identifiers, referenced_identifiers
   :undoc-members:
```

`source` is UTF-8 bytes. `symbols`, `imports`, and `scope_graph` contain extracted
structure. `has_errors` records parsing problems. `embedded_regions` contains
`contextcraft.ast.EmbeddedRegion` values with a source range, language class,
and a separately parsed AST; ranges inside that AST are local to its source.

## Secret metadata

`SecretMatch` is a frozen Pydantic model. It records `kind` (`SecretKind`), a
one-based `line_number`, `redacted_placeholder`, and `masked_preview` rather
than the original secret value.

```{eval-rst}
.. autoclass:: contextcraft.SecretKind
   :members:
   :undoc-members:
```
