# Compilation SDK

## ContextCraft

```{eval-rst}
.. autoclass:: contextcraft.ContextCraft

.. py:method:: contextcraft.ContextCraft.compile(path: str | pathlib.Path) -> contextcraft.models.Artifact

   Compile a repository and return a budgeted artifact.
```

Pass a `Config` instance to set the budget, focus, file exclusions, and output
format. The compiler uses that instance directly; it does not copy it.

```python
from contextcraft import ContextCraft
from contextcraft.config import Config, OutputFormat

config = Config(
    budget_tokens=16000,
    focus_query="authentication",
    exclude_patterns=["tests/**"],
    output_format=OutputFormat.XML,
)
compiler = ContextCraft(config)
artifact = compiler.compile(".")
print(artifact.content)
print(artifact.tokens)
```

`compile(path)` accepts a string or `pathlib.Path`. A directory is scanned
recursively. If a file is supplied, its parent directory is scanned, not just
that file. A Git checkout is not required.

Each call indexes files, loads and optionally redacts source, resolves imports,
ranks the dependency graph, renders fidelity tiers, allocates the budget, and
formats an [Artifact](models.md). It reads the repository again on every call;
there is no snapshot or `analyze()` API.

To change settings for another compilation, update the shared config or create
a new compiler. Pass language classes through the keyword-only `languages`
argument to replace the built-in language set; see [Language Extension API](languages.md).

## Configuration

```{eval-rst}
.. autoclass:: contextcraft.config.Config
```

`Config` is a mutable, keyword-only `msgspec.Struct`. Use enum members for
`output_format` and `tokenizer_encoding` when constructing it directly.

| Field                   | Default                         | Meaning                                                               |
| :---------------------- | :------------------------------ | :-------------------------------------------------------------------- |
| `budget_tokens`         | `16000`                         | Positive integer output token budget                                  |
| `focus_query`           | `None`                          | Query used to prefer relevant files                                   |
| `focus_files`           | `[]`                            | Repository-relative paths, filenames, directories, or globs to prefer |
| `output_format`         | `OutputFormat.MARKDOWN`         | Artifact format                                                       |
| `exclude_patterns`      | `[]`                            | Additional ignore globs                                               |
| `respect_gitignore`     | `True`                          | Respect Git ignore rules during indexing                              |
| `redact_secrets`        | `True`                          | Redact recognized secrets before source analysis                      |
| `max_file_size_bytes`   | `1048576`                       | Positive maximum source size in bytes                                 |
| `tokenizer_encoding`    | `TokenizerEncoding.CL100K_BASE` | Tiktoken encoding for token accounting                                |
| `allow_token_estimates` | `False`                         | Allow approximate counts if tokenization fails                        |

Direct construction and assignment do not validate field types or constraints.
For validated input, use `msgspec.convert()` or a typed msgspec decoder. Unknown
fields are rejected during typed decoding or conversion. Budgets are integers;
there is no shorthand parser for values such as `"16k"`.

```python
import msgspec

from contextcraft.config import Config

config = msgspec.convert(
    {"budget_tokens": 8000, "output_format": "json"},
    type=Config,
)
```

```{eval-rst}
.. autoclass:: contextcraft.config.OutputFormat
   :members:

.. autoclass:: contextcraft.config.TokenizerEncoding
   :members:
```

## Pipeline stages

Use the stages directly when you need the index, import resolutions, file
scores, or rendered tiers before formatting. Pass records from the same analysis
through the pipeline so their file, module, and import IDs agree.

```python
from contextcraft.config import Config
from contextcraft.formatter import ArtifactFormatter
from contextcraft.graph import GraphBuilder, GraphScorer
from contextcraft.imports import ImportResolver
from contextcraft.index import Indexer
from contextcraft.optimizer import BudgetAllocator
from contextcraft.source import SourceLoader
from contextcraft.tiers import TierRenderer

config = Config(budget_tokens=8000)
index = Indexer().index(".", config)
source = SourceLoader().load(index, config)
resolutions = ImportResolver().resolve(index, source)
graph = GraphBuilder().build(index, source, resolutions)
scores = GraphScorer().score(index, source, graph, config)
tiers = TierRenderer().render(index, source, config)
selection = BudgetAllocator().allocate(index, tiers, scores, config)
artifact = ArtifactFormatter().format(index, tiers, scores, selection, config)
```

Indexing records detected language implementations in `index.languages`.
Later stages require an entry for every non-null `File.language_id` they use;
a missing implementation raises `KeyError`. Files with no detected language
retain their source without language-specific analysis.

```{eval-rst}
.. autoclass:: contextcraft.index.Indexer
   :members: index

.. autoclass:: contextcraft.source.SourceLoader
   :members: load

.. autoclass:: contextcraft.imports.ImportResolver
   :members: resolve

.. autoclass:: contextcraft.graph.GraphBuilder
   :members: build

.. autoclass:: contextcraft.graph.GraphScorer

.. py:method:: contextcraft.graph.GraphScorer.score(index: contextcraft.models.Index, source: contextcraft.models.Source, graph: rustworkx.PyDiGraph, config: contextcraft.config.Config) -> dict[int, float]

   Return personalized PageRank scores keyed by file ID. Query matching uses
   paths, signatures, docstrings, and source. An empty graph returns an empty
   mapping.

.. autoclass:: contextcraft.tiers.TierRenderer
   :members: render

.. autoclass:: contextcraft.optimizer.BudgetAllocator
   :members: allocate

.. autoclass:: contextcraft.formatter.ArtifactFormatter
   :members: file_cost, render, directory_tree, format
```

Allocation uses framed token costs to choose tiers. `ArtifactFormatter.format()`
checks the complete serialized output and may downgrade tiers or shorten the
path listing to fit the budget. `render()` alone does not enforce a budget.

## Token counting

```{eval-rst}
.. py:class:: contextcraft.tiers.TokenCounter(encoding: contextcraft.config.TokenizerEncoding, *, allow_estimates: bool = False)

   Count tokens with the requested encoding and an optional fallback estimate.
   The ``used_estimates`` attribute stays true after any call uses an estimate.

   .. py:method:: count(content: str) -> int

      Return the token count, or zero for empty content. Special-token text is
      counted as ordinary text.
```

Exact tiktoken counts are the default. Loading an encoding may download its
data. If `allow_estimates=True`, loading or encoding failures can fall back to
an estimate; invalid encoding names still raise `ValueError`. Check
`used_estimates` on the counter or `token_counts_estimated` on the artifact
before treating the budget as exact.

## Errors

The SDK propagates pipeline and dependency exceptions; it does not wrap them in
a package-specific exception hierarchy.

- `OSError`, including `FileNotFoundError` and `NotADirectoryError`, reports
  unreadable paths or sources.
- `ValueError` reports an invalid allocation budget, framing that cannot fit,
  or an invalid tokenizer encoding. Lower-level stages also validate file
  coverage and score values.
- `KeyError` reports missing referenced records or detected language implementations.
- `msgspec.ValidationError` reports invalid input during typed decoding or conversion.

Other dependency errors, including walker, parser, and tokenizer failures,
propagate unless the relevant stage explicitly handles them. Enabling secret
redaction does not guarantee that every secret is detected.
