from __future__ import annotations

import heapq
from dataclasses import dataclass

from contextcraft.elider import FidelityLevel
from contextcraft.models import CompilationConfig, FileAnalysis


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

    Greedy marginal upgrades and bounded pairwise swaps approximate the
    multiple-choice knapsack objective; they do not guarantee a global optimum.
    Wrapper costs are estimates. ArtifactFormatter enforces the emitted budget.
    """

    FILE_WRAPPER_OVERHEAD_TOKENS: int = 18
    BASE_DOCUMENT_OVERHEAD_TOKENS: int = 115
    PER_FILE_TREE_ENTRY_TOKENS: int = 9
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
                used_tokens = self._greedy_marginal_allocation(files, net_budget)
                used_tokens = self._local_search_refinement(files, used_tokens, net_budget)
                used_tokens = self._greedy_marginal_allocation(files, net_budget, used_tokens)

        return BudgetAllocationSummary(
            budget_tokens=budget,
            tree_overhead_tokens=estimated_tree_overhead,
            net_code_budget=net_budget,
            allocated_code_tokens=used_tokens,
            total_estimated_tokens=estimated_tree_overhead + used_tokens,
            objective_score=self._compute_total_objective(files),
        )

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

    @staticmethod
    def tier_utility(file_obj: FileAnalysis, level: FidelityLevel) -> float:
        return file_obj.pagerank_score * level.semantic_utility

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
                    for up_idx, up_file in enumerate(files):
                        if up_idx == down_idx:
                            continue
                        up_current = up_file.selected_fidelity
                        for target in self._ORDERED_TIERS:
                            if target <= up_current:
                                continue
                            cost = self._effective_tier_cost(
                                up_file, target
                            ) - self._effective_tier_cost(up_file, up_current)
                            if cost > available:
                                continue
                            gain = (
                                self.tier_utility(up_file, target)
                                - self.tier_utility(up_file, up_current)
                                - loss
                            )
                            if gain > best_gain:
                                best_gain = gain
                                best_swap = down_idx, down_level, up_idx, target, cost - freed
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
