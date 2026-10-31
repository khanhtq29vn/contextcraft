---
title: Mathematics and algorithms
description: The scoring equations, greedy tier allocation, and final budget checks used by ContextCraft.
---

ContextCraft ranks files, then assigns source detail under a token budget. The sections below explain the algorithms, their constants, and their stopping rules. The allocator is greedy, not an exact knapsack solver.

## Notation and dependency graph

Let `V` be the indexed files, `N = |V|`, and `B` the artifact's token budget. A directed edge `i → j` means file `i` depends on local file `j`. Duplicate edges collapse into one edge, and self-dependencies are excluded. All indexed files remain graph nodes, including files without readable source.

Write `d(i)` for the number of outgoing dependencies of file `i`. Language implementations determine which local dependencies can be resolved. The graph comes from static analysis rather than runtime calls.

## 1. Field-weighted lexical relevance

The focus query and document fields use the same lexical tokenizer. It lowercases words and retains both whole identifiers and components split at underscores, camel-case boundaries, and acronym boundaries. Components shorter than two characters are omitted, and duplicate tokens within one matched word are counted once. Query terms are deduplicated into a set $Q$.

Each file has four searchable fields:

| Field                           | Weight `w(f)` |
| :------------------------------ | ------------: |
| Repository-relative path        |           5.0 |
| Captured declaration signatures |           4.0 |
| Captured documentation          |           2.5 |
| Complete readable source        |           1.0 |

Overlapping captured ranges are merged within a field before counting. A term can still contribute through several fields, for example through both a signature and the complete source.

For query term `t`, define `tf(t,i,f)` as its frequency in field `f` of file `i`, `L(i,f)` as that field's lexical token count, and $\overline{L}(f)$ as the mean field length across all indexed files. Missing fields have length zero.

The normalized, field-weighted frequency is:

$$
F(t,i) = \sum_{f:\,\mathrm{tf}(t,i,f)>0}
\frac{w(f)\,\mathrm{tf}(t,i,f)}
{1-b+b\,L(i,f)/\overline{L}(f)},
\qquad b=0.75
$$

Only fields with a nonzero term frequency contribute, so fields absent from every document do not cause division by zero.

Let `df(t)` count files containing `t` in at least one field. The inverse document frequency and BM25F relevance are:

$$
\begin{aligned}
\mathrm{IDF}(t) &= \ln\!\left(1+\frac{N-\mathrm{df}(t)+0.5}{\mathrm{df}(t)+0.5}\right) \\
\mathrm{lexical}(i) &= \sum_{t\in Q}\mathrm{IDF}(t)
\frac{F(t,i)(k_1+1)}{F(t,i)+k_1},\qquad k_1=1.2
\end{aligned}
$$

The sums over $t$ range over $Q$. An empty query gives every file a lexical score of zero. These lexical tokens measure relevance. The output budget uses BPE tokens instead.

## 2. Focus preferences and one-hop diffusion

Let `focused(i)` equal `1` when a file matches any configured focus path, filename, directory, or glob, and `0` otherwise. Multiple matching patterns do not stack their bonuses.

The initial preference is:

$$
p_0(i)=1+\mathrm{focused}(i)+3.5\,\mathrm{lexical}(i)
$$

If there are query terms or a matched focus file, the scorer diffuses preference to dependencies. Let `m` be the upper median of the initial preferences: the sorted element at zero-based index `floor(N / 2)`.

For each file `i` with $p_0(i)>1.5m$ and `d(i) > 0`, add the following amount to every dependency `j` of `i`:

$$
\begin{aligned}
\mathrm{contribution}(i\to j) &= \frac{0.3\,(p_0(i)-m)}{d(i)} \\
p_1(j) &= p_0(j)+\sum_{\substack{i\to j\\i\text{ eligible}}}
\mathrm{contribution}(i\to j)
\end{aligned}
$$

All contributions use the original preferences, so this step spreads focus one hop rather than recursively. It adds preference to dependencies without subtracting from the originating file. If diffusion is skipped, $p_1=p_0$.

Normalize the result into the personalization distribution:

$$
p(i)=\frac{p_1(i)}{\sum_{j\in V}p_1(j)}
$$

Focus changes ranking without forcing a file into the artifact or assigning it a particular fidelity tier.

## 3. Personalized PageRank

Initialize $r_0=p$. At iteration `k`, let $D_k$ be the rank mass in dangling nodes, which have no outgoing dependencies:

$$
\begin{aligned}
D_k &= \sum_{i:\,d(i)=0}r_k(i) \\
r_{k+1}(j) &= (1-\alpha+\alpha D_k)\,p(j)
+\alpha\sum_{i\to j}\frac{r_k(i)}{d(i)},\qquad\alpha=0.85
\end{aligned}
$$

Rank flows from importing files toward their dependencies. Dangling mass is redistributed according to the personalization distribution, rather than uniformly.

Iteration stops after 200 updates or when the total absolute change satisfies:

$$
\sum_{j\in V}\left|r_{k+1}(j)-r_k(j)\right|<N\times10^{-6}
$$

The final ranks are normalized to sum to one. An empty index returns an empty score map without running these equations. Each PageRank update traverses the nodes and edges, taking `O(N + |E|)` work.

## 4. Fidelity utility and token costs

Each file has a path-only tier and, when readable source exists, richer tiers. Utilities are fixed relative weights, not measured probabilities of usefulness:

| Tier   | Utility `u(l)` |
| :----- | -------------: |
| `TREE` |           0.00 |
| `SIGS` |           0.45 |
| `SKEL` |           0.82 |
| `FULL` |           1.00 |

The selection's score-weighted utility is:

$$
U(\mathrm{selection})=\sum_{i\in V}r(i)\,u(\mathrm{selected}(i))
$$

The allocator favors increases in this utility per additional token. It does not guarantee the globally optimal selection.

The path listing is budgeted separately. A binary search chooses an index-ordered prefix whose additional serialized cost over empty framing fits within `floor(B / 10)`. If the resulting all-`TREE` artifact exceeds `B`, the listing is repeatedly halved. If empty framing still cannot fit, allocation returns an error.

For richer tiers, the allocator initially estimates framed cost as `ceil(framed_bytes / 4)`. Counting a selected tier replaces that estimate with a cached exact block cost. JSON block costs include a trailing comma. The `TREE` block cost is zero because paths are budgeted separately.

Raw block costs can decrease between tiers because escaping and labels affect serialization. Allocation uses a prefix maximum over available tiers to make costs nondecreasing:

$$
C(i,l)=\max_{\substack{h\le l\\h\text{ available}}}\mathrm{block\_cost}(i,h)
$$

For an upgrade from tier `a` to a richer tier `b`:

$$
\begin{aligned}
\mathrm{gain} &= r(i)\,(u(b)-u(a)) \\
\mathrm{cost} &= C(i,b)-C(i,a) \\
\mathrm{density} &= \frac{\mathrm{gain}}{\mathrm{cost}}
\end{aligned}
$$

A positive-gain, zero-cost upgrade has infinite density. Only positive-gain upgrades that fit the remaining budget are candidates.

## 5. Greedy allocation and lazy refinement

Each allocation pass follows this procedure:

1. Reset all files to `TREE` and reserve the framing and listing cost.
2. Find each file's highest-density affordable upgrade and push it into a max-heap. Upgrades can skip intermediate tiers.
3. Pop the highest-priority candidate. Apply it if it still fits the remaining budget.
4. Recompute that file's best affordable upgrade from its current tier and push it if one exists.
5. Continue until the heap is empty.
6. Count any selected tiers whose exact costs are not cached. Restart allocation if any cost was refined. Otherwise, return the selection.

Heap ties prefer greater gain, then lower cost, then lower file ID, then the lower target tier. This gives a defined ordering when candidates have equal density.

Every refinement pass caches at least one previously uncounted selected tier. With a finite number of files and available tiers, refinement terminates. Allocation can require multiple heap passes and exact tokenization of selected tiers. Final budget correction adds further rendering and counting.

## 6. Exact final budget enforcement

BPE token counts are not additive across separately rendered blocks. The formatter therefore serializes the complete artifact and counts it with the configured tokenizer.

If the result exceeds `B`, it considers every available lower tier for each selected file. For each downgrade, let $c_{\mathrm{current}}$ and $c_{\mathrm{lower}}$ be the exact framed block costs. It computes:

$$
\begin{aligned}
\mathrm{savings} &= \max(c_{\mathrm{current}}-c_{\mathrm{lower}},0) \\
\mathrm{loss} &= r(i)\,(u(\mathrm{current})-u(\mathrm{lower})) \\
\mathrm{downgrade\_density} &= \frac{\mathrm{loss}}{\mathrm{savings}}
\end{aligned}
$$

Candidates with zero savings are skipped. The formatter chooses the smallest loss per saved token. Ties prefer lower loss, then lower file ID, then the lower target tier.

After each downgrade, it renders and counts the complete artifact again. If no downgrade offers positive block savings, it halves the path listing. If the listing is empty and no such downgrade remains, it returns a budget error instead of oversized output.

A successful artifact satisfies `tokens(artifact) ≤ B` for the selected vocabulary. The current tokenizer uses exact final counts without a fallback to estimates. This guarantee does not extend to a different model's tokenizer, and the allocator need not spend every available token.

## Implementation reference

- [Dependency graph and ranking](../api/rust/contextcraft-ai-core/graph/)
- [Tier rendering and utility](../api/rust/contextcraft-ai-core/tiers/)
- [Budget allocation](../api/rust/contextcraft-ai-core/optimizer/)
- [Final formatting](../api/rust/contextcraft-ai-core/formatter/)
- [Token counting](../api/rust/contextcraft-ai-core/tokens/)
