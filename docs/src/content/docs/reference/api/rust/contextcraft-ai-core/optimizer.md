---
title: "contextcraft-ai-core::optimizer"
description: "Select fidelity tiers using score-weighted utility per token."
editUrl: false
sidebar:
  order: 73
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Select fidelity tiers using score-weighted utility per token.

## Structs

### <span id="struct.Selection"></span><code style="font-size: 0.85em">struct Selection</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `Default`, `PartialEq`, `Eq`

One available fidelity level for every indexed file.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `tiers` | `ArenaMap<FileId, FidelityLevel>` | Selected fidelity level for every file in the associated index. |
| `token_counts_estimated` | `bool` | Whether any costs used for this allocation were estimated. |

### <span id="struct.BudgetAllocator"></span><code style="font-size: 0.85em">struct BudgetAllocator</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Greedy tier allocator with lazy token-cost refinement.

#### Methods

##### <span id="BudgetAllocator.allocate"></span><code>allocate</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn allocate(
    index: &Index,
    tiers: &Tiers,
    scores: &ArenaMap<FileId, f64>,
    config: &Config,
) -> Result<Selection, Error>
```

Selects tiers by marginal utility per token and refines their cached costs.

This greedy allocation is not an exact knapsack solution. The formatter
must recount the complete output because BPE merges can span file blocks.

**Errors:**

Returns an error for inconsistent pipeline inputs, invalid scores,
unavailable tokenization, or a budget smaller than the output framing.

<details>
<summary>Source</summary>

```rust
    pub fn allocate(
        index: &Index,
        tiers: &Tiers,
        scores: &ArenaMap<FileId, f64>,
        config: &Config,
    ) -> Result<Selection, Error> {
        tiers.validate(index, config)?;
        validate_scores(index, scores)?;
        let counter = TokenCounter::new(config.tokenizer_encoding, config.allow_token_estimates)?;
        let mut selection = Selection {
            tiers: index
                .files
                .iter()
                .map(|(file, _)| (file, FidelityLevel::Tree))
                .collect(),
            token_counts_estimated: tiers.token_counts_estimated,
        };
        let mut tree = ArtifactFormatter::directory_tree(index, tiers, &counter, config)?;
        let mut overhead = counter.count(&ArtifactFormatter::render(
            index, tiers, &selection, &tree, config,
        )?)?;

        while overhead > config.budget_tokens.get() && !tree.is_empty() {
            tree.truncate(tree.len() / 2);
            overhead = counter.count(&ArtifactFormatter::render(
                index, tiers, &selection, &tree, config,
            )?)?;
        }

        if overhead > config.budget_tokens.get() {
            return Err(Error::BudgetTooSmall {
                budget: config.budget_tokens.get(),
                minimum: overhead,
            });
        }

        let mut upgrades = BinaryHeap::with_capacity(index.files.len());

        loop {
            let mut remaining = config.budget_tokens.get() - overhead;

            for (file, level) in selection.tiers.iter_mut() {
                *level = FidelityLevel::Tree;

                if let Some(upgrade) = Upgrade::best(file, *level, tiers, scores[file], remaining) {
                    upgrades.push(upgrade);
                }
            }

            while let Some(upgrade) = upgrades.pop() {
                if upgrade.cost <= remaining {
                    selection.tiers[upgrade.file] = upgrade.level;
                    remaining -= upgrade.cost;
                }

                if let Some(next) = Upgrade::best(
                    upgrade.file,
                    selection.tiers[upgrade.file],
                    tiers,
                    scores[upgrade.file],
                    remaining,
                ) {
                    upgrades.push(next);
                }
            }

            let mut refined = false;

            for (file, &level) in selection.tiers.iter() {
                let tier = tiers.files[file].levels[level as usize].as_ref().unwrap();

                if !tier.is_counted() {
                    let path = &tiers.files[file].levels[FidelityLevel::Tree as usize]
                        .as_ref()
                        .unwrap()
                        .content;
                    tier.count(path, level, &counter, config.output_format)?;
                    refined = true;
                }
            }

            // Each refinement caches a new cost, so this loop is bounded by the tier count.
            if !refined {
                selection.token_counts_estimated |= counter.used_estimates();
                return Ok(selection);
            }
        }
    }
```

</details>
