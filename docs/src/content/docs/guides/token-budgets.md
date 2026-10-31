---
title: Choose a token budget
description: Set a budget for the complete artifact and choose a tokenizer vocabulary.
---

The budget limits the complete serialized artifact, including code, framing, and path listings. It is not the model’s entire context allowance: leave room for instructions, conversation, and the response.

## Set the budget

```sh
contextcraft . --budget 8k -o context.md
```

Positive integers accept `k` and `m` suffixes. For example, `8k` means 8,000 tokens. The default is 16,000 tokens.

Start with a budget that fits your available context, then review the artifact. Increase the budget if important implementation details are missing. Each run analyzes the repository again.

## Choose the encoding

```sh
contextcraft . --budget 16k --encoding o200k_base -o context.md
```

The default is `cl100k_base`. Supported labels are `gpt2`, `r50k_base`, `p50k_base`, `p50k_edit`, `cl100k_base`, `o200k_base`, and `o200k_harmony`.

Token counts are specific to the chosen vocabulary. A count made with one encoding is not a guarantee for another model’s tokenizer.

The Rust tokenizer counts the complete serialized artifact, including source, path listings, and output framing. Final counts are exact, with no fallback to estimates. The allocator may retain estimated costs for unselected tiers, but it does not use those estimates as the final artifact count.

## When the budget is too small

Output framing itself requires tokens. If it cannot fit, ContextCraft reports an error rather than emitting an oversized artifact. Increase `--budget`, or [exclude files](../files/) to reduce the scope.

A larger budget allows more detail, though the allocator may leave some tokens unused. Use [focus](../focus/) when the task matters more than broad coverage.
