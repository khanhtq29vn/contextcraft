# Compilation pipeline

Compilation runs stage by stage across a repository rather than finishing one
file at a time, because import resolution, ranking, and budget allocation
depend on information from multiple files.

```{mermaid}
flowchart LR
    Index --> Source
    Source --> Resolutions[Import resolutions]
    Index --> Resolutions
    Resolutions --> Graph
    Graph --> Scores
    Source --> Scores
    Source --> Tiers
    Index --> Tiers
    Scores --> Selection
    Tiers --> Selection
    Selection --> Artifact
    Tiers --> Artifact
    Scores --> Artifact
```

Custom language implementations must be thread-safe when using multiple
workers. Parsers and mutable token counters are not shared between concurrent
file operations by the built-in Python implementation. More workers may not
improve CPU-bound Python work; benchmark representative repositories.

## Index files and detect languages

`Indexer` walks a directory using Git ignore rules, language exclusions, and
configured exclude patterns. It detects a language by suffix or exact filename,
assigns file IDs in sorted path order, and groups files under the nearest
project root identified by language metadata. The scan root is always a project
root.

The resulting `Index` holds absolute paths and focus-pattern matches, along
with detected implementations in `Index.languages`. Each file's non-null
`language_id` must point to an implementation in that mapping for later stages
to use, while unrecognized files can still supply text content without
language analysis.

Indexing does not read source content, and passing a file to `Indexer.index()`
or `ContextCraft.compile()` selects its parent directory for the scan.

## Load source and extract metadata

`SourceLoader` reads at most one byte beyond the configured size limit to
identify oversized files, then rejects those files along with invalid UTF-8
and binary control bytes. Rejected sources remain in the index without loaded
content.

When enabled, secret masking runs before language analysis and preserves byte
offsets and line endings so downstream parsers work against the same source.
Since recognition relies on patterns, it cannot guarantee that the output is
free of secrets.

For recognized languages, the loader calls `Language.analyze()` to extract
docstrings, imports, and outline spans. Python parses each file once and runs
one combined query, sharing declaration captures between signatures and
skeletons. The loader retains byte spans and indentation, not parse trees or
rendered outlines. Ranking and tier rendering build outlines from those spans
without parsing or querying again. Rendered text is not cached.

## Resolve imports and rank files

`ImportResolver` groups records by source language and asks each detected
implementation to resolve them against the index. Definite targets, ambiguous
files, and unresolved names remain separate.

`GraphBuilder` creates a node for every indexed file and an edge from importer
to each definite dependency. `GraphScorer` combines this structure with optional
focus preferences to compute personalized PageRank. The
[current algorithm](algorithm.md) describes the scoring formulas.

## Render tiers

`TierRenderer` gives every indexed file a path-only `TREE` tier, adding
`FULL`, `SKEL`, and `SIGS` candidates when source was loaded. Language
implementations produce the outlines, while files with no detected language
reuse full text. An empty or oversized outline falls back to the next richer
tier.

Each tier stores both its content-only token count and its framed cost,
including escaping, headers, fences, and separators for the configured output
format. File workers calculate these costs during rendering. Even when tiers
share content, their labels can give them different framed costs.

## Allocate and format

Starting with every file at `TREE`, `BudgetAllocator` weighs each rank against
the cost of richer tiers and chooses upgrades that offer more weighted utility
per added token. It reads the precomputed framed costs rather than tokenizing
every tier again. The method is a heuristic rather than an exact knapsack
solver.

`ArtifactFormatter` serializes the selected tiers and counts the complete
result, lowering fidelity or shortening the path listing until the output
fits. The returned `Artifact` records that final output, its token count and
selected tiers, and whether any counts were estimated.

Final budget enforcement belongs to the formatter rather than allocation
alone, although a check based on estimates still cannot guarantee the true
tokenizer count. To run these steps separately, see [Pipeline
stages](../reference/api/stages.md).
