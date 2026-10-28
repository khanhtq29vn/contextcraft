# Current algorithm

ContextCraft separates the question of which files matter most from how much
of each file will fit. It first ranks files using resolved imports and
optional focus matches, then allocates space using those ranks, four fidelity
levels, and the costs of the chosen output format.

This page describes the implementation after the architecture rewrite. For the
previous design, see [Historical algorithm](algorithm-old.md).

## 1. Build an import graph

The graph contains a node for every indexed file, even when its source could
not be loaded. A definite import from file $i$ to file $j$ creates a directed
edge $i \to j$ with weight `1.0`, merging repeated imports between the same
files into one edge and omitting self-imports and ambiguous targets.

Because edges point toward dependencies, a file imported by several important
files can gain rank even without matching the focus query. The current graph
has no symbol-reference or reverse-import edges, and test files receive no
special penalty.

## 2. Score query matches with BM25F

When a focus query is present, the scorer tokenizes the query and four fields
for each file:

| Field                    | Weight |
| :----------------------- | -----: |
| Repository-relative path |    5.0 |
| Rendered signatures      |    4.0 |
| Extracted docstrings     |    2.5 |
| Loaded source            |    1.0 |

Tokenization lowercases words of at least two characters and adds parts split
from snake_case and CamelCase names, counting each query term only once. Even
when source could not be loaded, a file can still match through its path.

Let $n_{ift}$ be the count of term $t$ in field $f$ of file $i$, $L_{if}$ the
field length, and $\overline{L_f}$ the average field length across indexed
files. The combined, length-normalized frequency is

$$
F_{it} = \sum_f w_f
\frac{n_{ift}}{1-b+bL_{if}/\overline{L_f}},
\qquad b=0.75.
$$

Only fields containing the term contribute. If $N$ files are indexed and
$d_t$ contain the term in any field, its inverse document frequency is

$$
I_t = \log\left(1+\frac{N-d_t+0.5}{d_t+0.5}\right).
$$

The file's lexical score is

$$
s_i = \sum_{t \in q} I_t
\frac{F_{it}(k_1+1)}{F_{it}+k_1},
\qquad k_1=1.2.
$$

This favors matches in paths and declarations while reducing the advantage a
long file would get from repeating a term. Without query terms, all lexical
scores are zero.

## 3. Build PageRank preferences

Before normalization, each file receives preference

$$
p_i = 1 + \mathbf{1}_{i\text{ matches a focus-file pattern}} + 3.5s_i.
$$

Matching several focus patterns still adds only one point to a file's
preference, without excluding other files or forcing a particular tier.

When a query or focus-file match exists, preferences also spread one hop
toward dependencies. With $m$ denoting the upper median of the original
preferences, each node satisfying $p_i > 1.5m$ adds a total of $0.3(p_i-m)$ to
its outgoing neighbors in proportion to edge weights. This single diffusion
step increases dependency preferences without reducing the matching file's own
preference.

The scorer normalizes the resulting preferences and calls rustworkx PageRank
with damping factor $0.85$, using the same distribution for dangling nodes to
obtain one rank $r_i$ per graph node. Without focus, initial preferences are
uniform, but the graph structure can still produce different ranks.

## 4. Render candidate tiers

Loaded files have up to four useful representations:

| Tier   | Utility $u$ | Representation                         |
| :----- | ----------: | :------------------------------------- |
| `TREE` |        0.00 | No file content                        |
| `SIGS` |        0.45 | Declaration outline                    |
| `SKEL` |        0.82 | Outline with retained documentation    |
| `FULL` |        1.00 | Loaded source after optional redaction |

Files without loaded source have only `TREE`, while loaded files with no
recognized language reuse full source for their compressed tiers. An outline
also reuses the next richer tier whenever it is empty or has more content
tokens, so different fidelity levels can contain identical text.

## 5. Choose upgrades under the budget

The allocation objective is to maximize weighted utility:

$$
\max_{l_i} \sum_i r_i u(l_i)
\quad\text{subject to output cost}\le B.
$$

The implementation approximates this multiple-choice knapsack objective
without guaranteeing the global optimum.

First, the formatter finds a prefix of relative paths in file-ID order whose
added cost, measured above empty document framing, fits within one tenth of
$B$. The allocator reserves the resulting overhead and shortens the listing if
necessary, raising `ValueError` if even empty framing cannot fit.

Starting from `TREE` for every file, the allocator measures richer tiers with
their format-specific framing and escaping included. It then takes a running
maximum across increasing fidelity so that a richer tier never appears cheaper
during allocation.

For an upgrade from tier $l$ to $l'$, the priority is

$$
\rho(i,l\to l') =
\frac{r_i\bigl(u(l')-u(l)\bigr)}{C(i,l')-C(i,l)}.
$$

The allocator queues each file's best affordable upgrade in a heap and
repeatedly takes the highest-priority candidate, allowing upgrades to skip
levels. Positive-utility upgrades with no added cost receive infinite
priority. After accepting an upgrade it queues the file's next best option, or
looks for a cheaper alternative when a queued candidate no longer fits.

This favors useful outlines over expensive full bodies when the latter add
little weighted utility per token. There is no pairwise-swap refinement in the
current allocator.

## 6. Verify the serialized artifact

Adding separately counted blocks does not always predict the token count of
their concatenation. The formatter therefore renders the complete artifact and
counts it again.

When the result is too large, the formatter repeatedly chooses the downgrade
with the smallest weighted utility loss per framed token saved until the
output fits. Once no useful downgrade remains, it halves the path listing
instead, raising `ValueError` if even empty framing cannot fit.

The artifact records the tiers that survive this final check, emitting
selected file blocks in file-ID order rather than rank order. Since the path
listing is budgeted separately, a `TREE` selection does not guarantee a
visible entry for that file.

## Exact counts and estimates

Token counting tries tiktoken first and falls back to estimates on loading or
encoding failures by default, although invalid encoding names still raise
`ValueError`. The fallback combines a lexical piece count with a UTF-8
byte-length heuristic, which cannot guarantee a true token bound for the
configured tokenizer.

Check `Artifact.token_counts_estimated` before relying on an exact budget, or
require exact counts in an SDK run with `Config(allow_token_estimates=False)`.
The CLI does not expose that policy as a switch.
