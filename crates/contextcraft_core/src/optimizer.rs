//! Select fidelity tiers using score-weighted utility per token.

use std::cmp::Ordering;
use std::collections::BinaryHeap;

use la_arena::ArenaMap;

use crate::Config;
use crate::error::Error;
use crate::formatter::ArtifactFormatter;
use crate::index::{FileId, Index};
use crate::tiers::{FidelityLevel, Tiers};
use crate::tokens::TokenCounter;

/// One available fidelity level for every indexed file.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Selection {
    /// Selected fidelity level for every file in the associated index.
    pub tiers: ArenaMap<FileId, FidelityLevel>,
    /// Whether any costs used for this allocation were estimated.
    pub token_counts_estimated: bool,
}

impl Selection {
    pub(crate) fn validate(&self, index: &Index, tiers: &Tiers) -> Result<(), Error> {
        if self.tiers.iter().count() != index.files.len()
            || index.files.iter().any(|(file, _)| {
                self.tiers
                    .get(file)
                    .and_then(|&level| {
                        tiers
                            .files
                            .get(file)
                            .and_then(|tiers| tiers.levels[level as usize].as_ref())
                    })
                    .is_none()
            })
        {
            return Err(Error::InvalidPipeline(
                "select an available tier for every indexed file",
            ));
        }

        Ok(())
    }
}

/// Greedy tier allocator with lazy token-cost refinement.
#[derive(Debug)]
pub struct BudgetAllocator;

impl BudgetAllocator {
    /// Selects tiers by marginal utility per token and refines their cached costs.
    ///
    /// This greedy allocation is not an exact knapsack solution. The formatter
    /// must recount the complete output because BPE merges can span file blocks.
    ///
    /// # Errors
    ///
    /// Returns an error for inconsistent pipeline inputs, invalid scores,
    /// unavailable tokenization, or a budget smaller than the output framing.
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
}

pub(crate) fn validate_scores(index: &Index, scores: &ArenaMap<FileId, f64>) -> Result<(), Error> {
    if scores.iter().count() != index.files.len()
        || index.files.iter().any(|(file, _)| {
            scores
                .get(file)
                .is_none_or(|score| !score.is_finite() || *score < 0.0)
        })
    {
        return Err(Error::InvalidPipeline(
            "provide finite, nonnegative scores for every indexed file",
        ));
    }

    Ok(())
}

#[derive(Debug)]
struct Upgrade {
    density: f64,
    gain: f64,
    cost: usize,
    file: FileId,
    level: FidelityLevel,
}

impl Upgrade {
    fn best(
        file: FileId,
        current: FidelityLevel,
        tiers: &Tiers,
        score: f64,
        remaining: usize,
    ) -> Option<Self> {
        let mut best = None;
        let mut cost = 0;
        let mut current_cost = 0;

        for level in FidelityLevel::ALL {
            let Some(tier) = tiers.files[file].levels[level as usize].as_ref() else {
                continue;
            };
            // Escaping and labels can make raw framed costs nonmonotonic.
            cost = cost.max(tier.framed_tokens());

            if level <= current {
                current_cost = cost;
                continue;
            }

            let delta = cost - current_cost;
            let gain = score * (level.semantic_utility() - current.semantic_utility());

            if delta <= remaining && gain > 0.0 {
                let upgrade = Self {
                    density: if delta == 0 {
                        f64::INFINITY
                    } else {
                        gain / delta as f64
                    },
                    gain,
                    cost: delta,
                    file,
                    level,
                };

                if best.as_ref().is_none_or(|best| upgrade.cmp(best).is_gt()) {
                    best = Some(upgrade);
                }
            }
        }

        best
    }
}

impl Ord for Upgrade {
    fn cmp(&self, other: &Self) -> Ordering {
        self.density
            .total_cmp(&other.density)
            .then_with(|| self.gain.total_cmp(&other.gain))
            .then_with(|| other.cost.cmp(&self.cost))
            .then_with(|| other.file.cmp(&self.file))
            .then_with(|| other.level.cmp(&self.level))
    }
}

impl PartialOrd for Upgrade {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl PartialEq for Upgrade {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other).is_eq()
    }
}

impl Eq for Upgrade {}
