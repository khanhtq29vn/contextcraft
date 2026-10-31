# ContextCraft Python bindings

Compress a local repository into token-budgeted context using the Rust core.
The SDK requires Python 3.10 or newer and has no Python runtime dependencies.
The optional Cyclopts and Rich CLI requires Python 3.10 or newer.

## Install

```sh
pip install "contextcraft-ai[cli]"
contextcraft . --budget 8k --focus "authentication" -o context.md
python -m contextcraft . --format json --budget 16k
```

Install only the SDK with `pip install contextcraft-ai`.

The CLI accepts directories, not individual source files or remote URLs. It uses
`Config` and `ContextCraft.run()`, the same API as the SDK.

## Python API

```python
from pathlib import Path
from contextcraft import Config, ContextCraft, OutputFormat, TokenCounter

config = Config(
    budget_tokens=8_000,
    focus_query="authentication",
    focus_files=["src/auth"],
    output_format=OutputFormat.MARKDOWN,
)
pipeline = ContextCraft(config)
analysis = pipeline.run(Path("."))

print(analysis.artifact.content)
print(analysis.artifact.tokens)
assert TokenCounter().count(analysis.artifact.content) == analysis.artifact.tokens

# Changes apply to the next run, which rereads and reanalyzes the repository.
pipeline.config.budget_tokens = 16_000
```

`ContextCraft` retains the supplied `Config`. Each run copies its settings before
releasing the GIL for Rust processing. Concurrent Python code can run while the
core analyzes sources. Native result conversion takes place with the GIL held.

Configuration attributes are writable. List attributes return copies, so assign
`config.focus_files = ["src/auth", "src/session"]` rather than appending to a
returned list. Result attributes are read-only. Their lists and dictionaries are
copies containing shared snapshot objects.

### Configuration

| Attribute               | Default                         | Meaning                                                                                                                                 |
| ----------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `enable_parallel`       | `True`                          | Use Rayon for source analysis and tier rendering.                                                                                       |
| `budget_tokens`         | `16000`                         | Maximum tokens in the complete serialized artifact. Must be positive.                                                                   |
| `focus_query`           | `None`                          | Task description used for lexical relevance and personalized ranking.                                                                   |
| `focus_files`           | `[]`                            | Paths, filenames, directories, or globs to favor. Matching does not guarantee inclusion.                                                |
| `output_format`         | `OutputFormat.MARKDOWN`         | Markdown, XML, or JSON serialization.                                                                                                   |
| `exclude_patterns`      | `[]`                            | Repository-relative `ignore::overrides` globs without a leading exclusion marker.                                                       |
| `respect_gitignore`     | `True`                          | Honor Git exclusion rules. Language-specific exclusions still apply when disabled.                                                      |
| `redact_secrets`        | `True`                          | Redact recognized secret types before parsing, preserving byte offsets and line breaks. Detection does not cover every possible secret. |
| `max_file_size_bytes`   | `1048576`                       | Source and manifest read limit in bytes. Must be positive.                                                                              |
| `tokenizer_encoding`    | `TokenizerEncoding.CL100K_BASE` | Vocabulary used for token accounting.                                                                                                   |
| `allow_token_estimates` | `True`                          | Permit estimated pipeline counts. The current tokenizer counts exactly without a fallback.                                              |

The format constants are `MARKDOWN`, `XML`, and `JSON`. Tokenizer constants are
`GPT2`, `R50K_BASE`, `P50K_BASE`, `P50K_EDIT`, `CL100K_BASE`, `O200K_BASE`, and
`O200K_HARMONY`. Fidelity constants are `TREE`, `SIGS`, `SKEL`, and `FULL`.
These native constants are hashable, but are not Python `enum.Enum` members.
Use `.as_str()` to obtain their configuration or output labels.

### Analysis results

`run()` returns a `RepositoryAnalysis` with these attributes:

- `index`: canonical root as a `pathlib.Path`, file and package dictionaries,
  workspace memberships, and sorted language IDs.
- `repository.sources`: readable source files keyed by file ID. Each `Source`
  has UTF-8 `bytes` after optional redaction and optional `Analysis` ranges.
- `graph.dependencies`: sorted `(importing_file_id, dependency_file_id)` pairs.
- `scores`: normalized file relevance scores keyed by file ID.
- `tiers`: rendered tiers, their output format, and their tokenizer vocabulary.
- `artifact`: serialized `content`, final `tokens`, `token_counts_estimated`, and
  `selected_tiers` keyed by file ID.

File and package IDs are integers local to one analysis. Do not combine IDs from
separate runs. Paths within file and package records are repository-relative
`pathlib.Path` objects. Outline ranges are half-open `(start, end)` UTF-8 byte
positions, not character positions.

```python
from contextcraft import FidelityLevel

for file_id, file in analysis.index.files.items():
    selected = analysis.artifact.selected_tiers[file_id]
    print(file.path, selected.as_str(), analysis.scores[file_id])

    full = analysis.tiers.files[file_id].levels.get(FidelityLevel.FULL)
    if full is not None:
        print(full.content)
```

Oversized, binary, and non-UTF-8 files remain indexed but have no readable source
entry. Unselected tiers may retain estimated `framed_tokens` costs even when the
final artifact count is exact. The final artifact is recounted as a whole.

The binding exports snapshots rather than Rust trait objects or mutable pipeline
stages. Reusing a `ContextCraft` does not cache repository analysis.

### Errors

- `OSError`, including `FileNotFoundError` and `NotADirectoryError`, reports
  filesystem failures. I/O errors retain the affected filename when available.
- `ValueError` reports zero numeric limits, invalid manifests, or output framing
  that cannot fit within the token budget.
- `OverflowError` reports negative integers or integers larger than native limits.
- `TypeError` reports unsupported argument names or types.
- `RuntimeError` reports traversal, parsing, or tokenizer failures not covered above.

Settings changed after construction are validated again when `run()` starts.

## CLI

Install the `cli` extra to enable Cyclopts parsing and Rich output. From this
workspace, run it with uv:

```sh
uv run --package contextcraft-ai --extra cli contextcraft . --budget 8k
```

```sh
contextcraft . --budget 8k --format markdown --focus "dependency resolution"
contextcraft . --focus-file src --focus-file '*.rs' --exclude docs -o context.md
contextcraft . --encoding o200k_base --no-parallel --no-token-estimates
```

Use `contextcraft --help` for all options. Budgets accept positive integers with
optional `k` or `m` suffixes. The CLI also supports `--no-redact`, `--no-gitignore`,
`--max-file-size-bytes`, `--quiet`, `--debug`, and `--version`.

The CLI uses the grouped help layout, compilation summary, and top-five
PageRank table from `origin/next`, adapted to the Rust-backed analysis snapshot.
The summary shows indexed and loaded files, skipped sources, encoding, source
tokens, output budget usage, compression, tier counts, timing, and output path.

Summary source-token counts are measured directly. They exclude file framing and
path listings, which are included in the final artifact count. Debug output
includes ranking, graph, and tier diagnostics. Unselected framed tier costs may
still be estimates and are labeled accordingly.

Artifact content goes to stdout or `--output`. Markdown is rendered with Rich
when stdout is a terminal. Piped output and saved files retain the original
artifact content. Summaries and diagnostics go to stderr. `--output -` means stdout. Output directories must already exist. Existing
output files may be overwritten and are excluded from scanning on repeated runs,
including when their names contain glob metacharacters. Output files use UTF-8
without newline translation.

Invalid arguments exit with status 2. Operational failures exit with status 1.
Successful runs exit with status 0. `--quiet` suppresses the summary, not warnings.

## Types and development

The wheel includes documented `.pyi` stubs and the PEP 561 `py.typed` marker.
Type checkers and editors can discover the native API without additional packages.

Development tools live in the workspace's optional `dev` dependency group. They
are not runtime dependencies of the published distribution.

```sh
# From the repository root.
uv sync --package contextcraft-ai --extra cli --group dev
uv run --package contextcraft-ai --extra cli --group dev maturin develop --manifest-path binding_python/Cargo.toml
uv run --package contextcraft-ai --extra cli --group dev pyrefly check binding_python/python/contextcraft
uv run --package contextcraft-ai --extra cli --group dev ruff check binding_python/python
cargo test --workspace --locked
uv build --package contextcraft-ai
```

Use `uv sync --no-dev` for a workspace installation without development tools or
CLI dependencies. Without the `cli` extra, the SDK still imports normally and
the command prints an installation hint.
