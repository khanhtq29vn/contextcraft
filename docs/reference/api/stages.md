# Pipeline stages

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

Later stages reuse the implementations recorded during indexing in
`index.languages`, requiring an entry for every non-null `File.language_id`
they encounter. A missing implementation raises `KeyError`, while files with
no detected language retain their source without language-specific analysis.

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

Tier rendering counts both content-only tokens and framed file costs, using
its file workers. Allocation reads those costs instead of tokenizing every tier
again. Formatting also reuses them when choosing downgrades, but counts the
complete serialized output to enforce the budget. Joining blocks can change
token boundaries, so precomputed file costs alone cannot guarantee a fit.

Use the same index, output format, and tokenizer encoding for rendering,
allocation, and formatting. A format or encoding mismatch raises `ValueError`.
Changing either requires rendering tiers again. Calling `render()` alone skips
budget enforcement.

`ArtifactFormatter.file_cost(path, content, level, counter, config)` counts one
file block using a repository-relative path and its rendered text. The tier
renderer uses it before the full `Tiers` record exists.

## Token counting

```{eval-rst}
.. py:class:: contextcraft.tokens.TokenCounter(encoding: contextcraft.config.TokenizerEncoding, *, allow_estimates: bool = True)

   Count tokens with the requested encoding and an optional fallback estimate.
   The ``used_estimates`` attribute stays true after any call uses an estimate.

   .. py:method:: count(content: str) -> int

      Return the token count, or zero for empty content. Special-token text is
      counted as ordinary text.
```

Token counting tries tiktoken first, potentially downloading encoding data,
and falls back to an estimate if loading or encoding fails. Invalid encoding
names still raise `ValueError` regardless of that fallback.

To require exact counts, set `allow_estimates=False` on the counter or
`allow_token_estimates=False` in `Config`. Otherwise, check the counter's
`used_estimates` or the artifact's `token_counts_estimated` flag before
relying on an exact budget.
