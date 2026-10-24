from __future__ import annotations

import heapq
import math
from bisect import bisect_right
from dataclasses import dataclass

from contextcraft.elider import FidelityLevel
from contextcraft.models import CompilationConfig, FileAnalysis
from contextcraft.utils import matches_path_patterns


@dataclass(frozen=True, slots=True)
class _MarginalUpgrade:
    to_level: FidelityLevel
    delta_utility: float
    delta_tokens: int
    density: float


@dataclass(slots=True)
class BudgetAllocationSummary:
    """Estimated allocation costs before format-specific budget verification."""

    budget_tokens: int
    tree_overhead_tokens: int
    net_code_budget: int
    allocated_code_tokens: int
    total_estimated_tokens: int
    objective_score: float


class TokenBudgetOptimizer:
    """Allocate whole-file fidelity tiers using PageRank-weighted utility.

    Declarations (SIGS, SKEL) are worth pagerank * semantic_utility * mass, where
    mass = full_tokens ** (1/3): a large central file exposes more structure than
    a tiny one, so its outline outbids tiny peripheral files. The bodies FULL adds
    keep their size-blind value, so a giant file's SKEL -> FULL step is no more
    attractive per token than before (God-object protection).

    Greedy marginal upgrades and bounded pairwise swaps approximate the
    multiple-choice knapsack objective; they do not guarantee a global optimum.
    Wrapper costs are estimates. ArtifactFormatter enforces the emitted budget.
    """

    FILE_WRAPPER_OVERHEAD_TOKENS: int = 18
    BASE_DOCUMENT_OVERHEAD_TOKENS: int = 115
    PER_FILE_TREE_ENTRY_TOKENS: int = 9
    CONTENT_MASS_EXPONENT: float = 1 / 3
    _ORDERED_TIERS: tuple[FidelityLevel, ...] = (
        FidelityLevel.TREE,
        FidelityLevel.SIGNATURES,
        FidelityLevel.SKELETON,
        FidelityLevel.FULL,
    )

    def __init__(self, config: CompilationConfig | None = None) -> None:
        self.config = config or CompilationConfig()

    def optimize(
        self, files: list[FileAnalysis], tree_overhead_tokens: int | None = None
    ) -> BudgetAllocationSummary:
        """Reset and mutate selected fidelities, leaving source and tiers intact.

        Tree overhead includes document framing. If it exhausts the budget,
        all files remain TREE and the formatter handles the remaining overflow.
        Files matching ``pinned_full_files`` are fixed first: all get SIGS, then
        SKEL, then FULL, highest PageRank first at each step, as far as the budget
        allows. The remaining files share what is left.
        """
        budget = self.config.budget_tokens
        if not files:
            return BudgetAllocationSummary(
                budget_tokens=budget,
                tree_overhead_tokens=0,
                net_code_budget=budget,
                allocated_code_tokens=0,
                total_estimated_tokens=0,
                objective_score=0.0,
            )
        estimated_tree_overhead = (
            tree_overhead_tokens
            if tree_overhead_tokens is not None
            else self.estimate_tree_overhead(len(files))
        )
        for file_obj in files:
            file_obj.selected_fidelity = FidelityLevel.TREE
        net_budget = max(0, budget - estimated_tree_overhead)
        used_tokens = 0
        if net_budget > 0:
            total_full_cost = sum(
                self._effective_tier_cost(file, FidelityLevel.FULL) for file in files
            )
            if total_full_cost <= net_budget:
                for file in files:
                    file.selected_fidelity = FidelityLevel.FULL
                used_tokens = total_full_cost
            else:
                pinned = [
                    file
                    for file in files
                    if matches_path_patterns(file.rel_path, self.config.pinned_full_files)
                ]
                used_tokens = self._pin_files(pinned, net_budget)
                # Pinned tiers are final; the solver only sees the remaining files.
                pinned_ids = {id(file) for file in pinned}
                free = [file for file in files if id(file) not in pinned_ids]
                used_tokens = self._greedy_marginal_allocation(free, net_budget, used_tokens)
                used_tokens = self._local_search_refinement(free, used_tokens, net_budget)
                used_tokens = self._greedy_marginal_allocation(free, net_budget, used_tokens)

        return BudgetAllocationSummary(
            budget_tokens=budget,
            tree_overhead_tokens=estimated_tree_overhead,
            net_code_budget=net_budget,
            allocated_code_tokens=used_tokens,
            total_estimated_tokens=estimated_tree_overhead + used_tokens,
            objective_score=self._compute_total_objective(files),
        )

    @classmethod
    def _pin_files(cls, pinned: list[FileAnalysis], net_budget: int) -> int:
        """Raise pinned files tier by tier, highest PageRank first; return the tokens used.

        Every pin whose signatures fit gets them before any pin gets a skeleton,
        and so on up to FULL, so a pin's signatures are never given up for another
        pin's richer tier. A pin whose next tier does not fit is skipped, and
        smaller pins may still be raised past it.
        """
        ranked = sorted(pinned, key=lambda item: (-item.pagerank_score, item.rel_path))
        used_tokens = 0
        for level in cls._ORDERED_TIERS[1:]:
            for file in ranked:
                delta = cls._effective_tier_cost(file, level) - cls._effective_tier_cost(
                    file, file.selected_fidelity
                )
                if used_tokens + delta <= net_budget:
                    file.selected_fidelity = level
                    used_tokens += delta
        return used_tokens

    @classmethod
    def estimate_tree_overhead(cls, num_files: int) -> int:
        return cls.BASE_DOCUMENT_OVERHEAD_TOKENS + num_files * cls.PER_FILE_TREE_ENTRY_TOKENS

    @classmethod
    def _effective_tier_cost(cls, file_obj: FileAnalysis, level: FidelityLevel) -> int:
        if level == FidelityLevel.TREE:
            return 0
        tier = file_obj.tiers.get(level)
        raw_tier_cost = tier.tokens if tier is not None else 0
        if raw_tier_cost <= 0:
            return 0
        return raw_tier_cost + cls.FILE_WRAPPER_OVERHEAD_TOKENS

    @classmethod
    def tier_utility(cls, file_obj: FileAnalysis, level: FidelityLevel) -> float:
        structure = min(level.semantic_utility, FidelityLevel.SKELETON.semantic_utility)
        bodies = level.semantic_utility - structure
        return file_obj.pagerank_score * (structure * cls._content_mass(file_obj) + bodies)

    @classmethod
    def _content_mass(cls, file_obj: FileAnalysis) -> float:
        full = file_obj.tiers.get(FidelityLevel.FULL)
        return math.pow(max(full.tokens if full is not None else 0, 1), cls.CONTENT_MASS_EXPONENT)

    def _greedy_marginal_allocation(
        self, files: list[FileAnalysis], net_budget: int, used_tokens: int = 0
    ) -> int:
        """Apply affordable upgrades by utility gained per token; return total cost."""
        upgrades: list[tuple[float, float, int, int, _MarginalUpgrade]] = []

        def enqueue_upgrade(index: int, available: int) -> None:
            file = files[index]
            current_level = file.selected_fidelity
            current_cost = self._effective_tier_cost(file, current_level)
            current_value = self.tier_utility(file, current_level)
            candidates: list[_MarginalUpgrade] = []
            for level in self._ORDERED_TIERS:
                if level <= current_level:
                    continue
                cost = self._effective_tier_cost(file, level) - current_cost
                gain = self.tier_utility(file, level) - current_value
                if cost <= available and gain > 0:
                    candidates.append(_MarginalUpgrade(level, gain, cost, gain / max(cost, 1)))
            if candidates:
                best = min(
                    candidates,
                    key=lambda item: (-item.density, -item.delta_utility, item.delta_tokens),
                )
                heapq.heappush(
                    upgrades, (-best.density, -best.delta_utility, best.delta_tokens, index, best)
                )

        for index in range(len(files)):
            enqueue_upgrade(index, net_budget - used_tokens)
        while upgrades:
            _, _, _, index, upgrade = heapq.heappop(upgrades)
            if used_tokens + upgrade.delta_tokens > net_budget:
                enqueue_upgrade(index, net_budget - used_tokens)
                continue
            file = files[index]
            file.selected_fidelity = upgrade.to_level
            used_tokens += upgrade.delta_tokens
            enqueue_upgrade(index, net_budget - used_tokens)
        return used_tokens

    def _local_search_refinement(
        self, files: list[FileAnalysis], used_tokens: int, net_budget: int
    ) -> int:
        """Trade one file's fidelity for another's when total utility increases."""
        for _ in range(25):
            best_gain = 1e-06
            best_swap: tuple[int, FidelityLevel, int, FidelityLevel, int] | None = None
            upgrades: list[tuple[int, int, FidelityLevel, float]] = []
            for up_idx, up_file in enumerate(files):
                current = up_file.selected_fidelity
                current_cost = self._effective_tier_cost(up_file, current)
                current_value = self.tier_utility(up_file, current)
                for target in self._ORDERED_TIERS:
                    if target > current:
                        upgrades.append(
                            (
                                self._effective_tier_cost(up_file, target) - current_cost,
                                up_idx,
                                target,
                                self.tier_utility(up_file, target) - current_value,
                            )
                        )
            upgrades.sort()
            costs = [upgrade[0] for upgrade in upgrades]
            best: list[tuple[float, int, FidelityLevel, int]] = []
            prefixes: list[tuple[tuple[float, int, FidelityLevel, int], ...]] = []
            for cost, up_idx, target, gain in upgrades:
                # Two distinct files suffice to exclude the file being downgraded.
                candidate = (-gain, up_idx, target, cost)
                existing = next((item for item in best if item[1] == up_idx), None)
                if existing is None or candidate < existing:
                    best = sorted([item for item in best if item[1] != up_idx] + [candidate])[:2]
                prefixes.append(tuple(best))

            for down_idx, down_file in enumerate(files):
                current = down_file.selected_fidelity
                current_cost = self._effective_tier_cost(down_file, current)
                current_value = self.tier_utility(down_file, current)
                for down_level in self._ORDERED_TIERS:
                    if down_level >= current:
                        break
                    freed = current_cost - self._effective_tier_cost(down_file, down_level)
                    if freed <= 0:
                        continue
                    loss = current_value - self.tier_utility(down_file, down_level)
                    available = net_budget - used_tokens + freed
                    position = bisect_right(costs, available) - 1
                    if position < 0:
                        continue
                    for negative_gain, up_idx, target, cost in prefixes[position]:
                        if up_idx == down_idx:
                            continue
                        gain = -negative_gain - loss
                        if gain > best_gain:
                            best_gain = gain
                            best_swap = down_idx, down_level, up_idx, target, cost - freed
                        break
            if best_swap is None:
                break
            down_idx, down_level, up_idx, target, delta_tokens = best_swap
            down_file = files[down_idx]
            down_file.selected_fidelity = down_level
            files[up_idx].selected_fidelity = target
            used_tokens += delta_tokens
        return used_tokens

    def _compute_total_objective(self, files: list[FileAnalysis]) -> float:
        return sum(self.tier_utility(f, f.selected_fidelity) for f in files)
