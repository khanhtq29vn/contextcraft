# Historical algorithm

This page describes the implementation before the architecture rewrite,
using [commit 61567d4](https://github.com/khanhtq29vn/contextcraft/tree/61567d4e811dd5eff225df377a0769cc414a3c3e)
as its reference. These classes, defaults, and heuristics are not the current
API. For present behavior, read [Current algorithm](algorithm.md).

The earlier implementation had the same broad goal: retain useful repository
context under a token budget. It combined richer AST records, a weighted
multigraph, and a greedy allocator with local swap refinement.

## AST records and language builders

A language registry selected extractors and tier builders that worked with
byte-backed AST records containing symbols, source ranges, imports, and
lexical scopes. Some languages also supplied embedded regions, allowing
JavaScript and CSS inside HTML to have their own parsed records.

The old `Elider` used language-specific builders to produce full source,
skeletons, and signatures. Supported builders could preserve source on parse
errors and trim unused named imports from declaration summaries. Those
behaviors depended on the language and were not guaranteed for arbitrary syntax.

The current implementation replaces those AST, registry, extractor, and
builder interfaces with static methods on `Language` that receive source
bytes.

## Weighted dependency graph

`DependencyGraphScorer` represented files as nodes in a NetworkX
`MultiDiGraph`, adding relationships from module imports and symbol
references. After indexing module-level bindings and declared names, it
considered references that could not be resolved within their local lexical
scope.

For each reference, the scorer preferred defining files among the source
file's import targets before considering other available definers, with
weights based on identifier weighting and the square root of reference
frequency. This cross-file matching was heuristic rather than a complete
language-level type or symbol resolver.

Import edges carried weight `6.0`, with reverse edges weighted at `0.9` when
the source was not a penalized test or benchmark file. Symbol references could
also have reverse edges at `0.15` times the forward weight, allowing several
relationships to connect the same pair of files.

In contrast, the current graph merges definite file-import edges with unit
weights and omits reverse and symbol-reference edges entirely.

## Query preferences and test dampening

The old scorer used BM25F over paths, signatures, docstrings, and source, with
field weights `5.0`, `4.0`, `2.5`, and `1.0`. It used $k_1=1.2$ and $b=0.75$.
Several additional preferences distinguished it from the current scorer:

- Filename priors favored files such as `core.py`, `models.py`, and project
  metadata over a uniform baseline.
- Lexical scores contributed a factor of `3.5`.
- Unfocused test and benchmark paths received a `0.02` multiplier. Explicit
  focus, or a query containing recognized test-related terms, could disable
  that penalty.
- Explicit focus-file matches added `20.0` after the penalty. Preferences had
  a floor of `0.05`.

For focused runs, a file above `1.5` times the median preference spread `0.3`
of its excess over the median to outgoing neighbors, weighted by their edges.
PageRank then used a custom power iteration with damping factor `0.85`.

The current scorer keeps BM25F, one-hop preference diffusion, and personalized
PageRank. It does not keep filename priors, test dampening, or the old focus-file
bonus, and it delegates PageRank to rustworkx.

## Allocation and pairwise swaps

`TokenBudgetOptimizer` approximated the multiple-choice knapsack objective:
choose one fidelity level per file to maximize PageRank-weighted utility within
a budget. It did not guarantee a global optimum.

Allocation began by reserving overhead, estimated at `115 + 9 × file_count`
tokens when no tree count was supplied, and adding `18` tokens of framing to
each positive code-tier cost. If every full-source tier fit, the allocator
selected them directly. Otherwise, it ran three steps:

1. Greedy upgrades, ordered by marginal utility per additional token.
2. Up to 25 local-search rounds trading one file's fidelity for another's when
   the exchange increased total utility and fit the remaining budget.
3. Another greedy pass to spend any remaining capacity.

For swap search, upgrades were sorted by cost. Prefix tables retained the best
candidates from two distinct files, and binary search found affordable options
after each possible downgrade. Keeping two files allowed the search to avoid
upgrading the file it was downgrading.

Final formatting still checked the emitted artifact rather than trusting the
allocator's wrapper estimates. The current allocator keeps the greedy upgrade
rule and final formatting check, but removes local swaps and measures
format-specific file framing costs instead of using that fixed wrapper
estimate.

## Reading older results

Old benchmark numbers and fidelity allocations describe that implementation,
its language support, and its input repository. They are not evidence of the
current implementation's speed or compression quality. Compare the same
repository, focus query, tokenizer, format, and budget before drawing a
performance conclusion across architectures.
