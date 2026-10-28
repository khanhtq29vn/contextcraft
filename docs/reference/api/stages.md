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

Allocation chooses tiers using framed token costs, but the complete serialized
output is checked by `ArtifactFormatter.format()`, which may downgrade tiers
or shorten the path listing to fit. Calling `render()` alone skips this budget
enforcement.

## Token counting

```{eval-rst}
.. py:class:: contextcraft.tiers.TokenCounter(encoding: contextcraft.config.TokenizerEncoding, *, allow_estimates: bool = True)

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
