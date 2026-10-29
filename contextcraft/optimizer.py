"""Allocate fidelity tiers using file scores and framed token costs."""

from __future__ import annotations

import heapq
import math

from contextcraft.config import Config
from contextcraft.formatter import ArtifactFormatter
from contextcraft.models import FidelityLevel, Index, Selection, Tiers
from contextcraft.tokens import TokenCounter


class BudgetAllocator:
    """Choose tier upgrades by weighing their utility against their token cost."""

    def allocate(
        self, index: Index, tiers: Tiers, scores: dict[int, float], config: Config
    ) -> Selection:
        """Allocate one available fidelity tier to every indexed file.

        Args:
            index: Files to allocate.
            tiers: Rendered tiers and framed costs for exactly the indexed files.
            scores: Finite, nonnegative weights for exactly the indexed files.
            config: Positive token budget, output format, and tokenizer options.

        Returns:
            A selection based on estimated framing overhead and marginal
            utility. Pass it to ArtifactFormatter.format to check the complete
            output against the budget; allocation alone does not guarantee a fit.

        Raises:
            ValueError: If the budget, file coverage, scores, or TREE tiers
                are invalid, the format or encoding differs from the rendered
                tiers, or output framing cannot fit the budget.
        """
        if config.budget_tokens <= 0:
            raise ValueError("Token budget must be positive")

        if set(tiers.files) != set(index.files) or set(scores) != set(index.files):
            raise ValueError("Render tiers and score all files before allocation")

        if (
            tiers.output_format != config.output_format
            or tiers.tokenizer_encoding != config.tokenizer_encoding
        ):
            raise ValueError("Render tiers with the same output format and encoding")

        if any(not math.isfinite(score) or score < 0 for score in scores.values()):
            raise ValueError("File scores must be finite and nonnegative")

        counter = TokenCounter(
            config.tokenizer_encoding,
            allow_estimates=config.allow_token_estimates,
        )

        formatter = ArtifactFormatter()
        selected = dict.fromkeys(index.files, FidelityLevel.TREE)
        tree = formatter.directory_tree(index, tiers, counter, config)
        overhead = counter.count(formatter.render(index, tiers, selected, tree, config))

        while tree and overhead > config.budget_tokens:
            tree = tree[: len(tree) // 2]
            overhead = counter.count(
                formatter.render(index, tiers, selected, tree, config)
            )

        if overhead > config.budget_tokens:
            raise ValueError("Token budget is too small for the output framing")

        available = config.budget_tokens - overhead
        costs = {}

        for file_id, file_tiers in tiers.files.items():
            if FidelityLevel.TREE not in file_tiers:
                raise ValueError(f"Missing TREE tier for file {file_id}")

            previous = 0
            costs[file_id] = {}

            for level in sorted(file_tiers):
                # Escaping can change token costs; use a monotonic upper bound.
                previous = max(previous, file_tiers[level].framed_tokens)

                costs[file_id][level] = previous

        upgrades: list[tuple[float, float, int, int, FidelityLevel]] = []

        def enqueue(file_id: int, remaining: int) -> None:
            current = selected[file_id]
            candidates = []

            for level, cost in costs[file_id].items():
                if level <= current:
                    continue

                delta = cost - costs[file_id][current]
                gain = scores[file_id] * (
                    level.semantic_utility - current.semantic_utility
                )

                if delta <= remaining and gain > 0:
                    density = gain / delta if delta else math.inf
                    candidates.append((-density, -gain, delta, file_id, level))

            if candidates:
                heapq.heappush(upgrades, min(candidates))

        for file_id in sorted(index.files):
            enqueue(file_id, available)

        used = 0

        while upgrades:
            _, _, delta, file_id, level = heapq.heappop(upgrades)

            if delta > available - used:
                enqueue(file_id, available - used)
                continue

            selected[file_id] = level
            used += delta
            enqueue(file_id, available - used)

        return Selection(
            tiers=selected,
            token_counts_estimated=tiers.token_counts_estimated
            or counter.used_estimates,
        )
