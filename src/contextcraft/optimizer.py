from __future__ import annotations

from dataclasses import dataclass

from contextcraft.elider import FidelityLevel
from contextcraft.models import CompilationConfig, FileAnalysis


@dataclass(frozen=True, slots=True)
class _MarginalUpgrade:
    file_idx: int
    from_level: FidelityLevel
    to_level: FidelityLevel
    delta_utility: float
    delta_tokens: int
    density: float


@dataclass(slots=True)
class BudgetAllocationSummary:
    budget_tokens: int
    tree_overhead_tokens: int
    net_code_budget: int
    allocated_code_tokens: int
    total_estimated_tokens: int
    objective_score: float


class TokenBudgetOptimizer:
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
        if net_budget <= 0:
            return BudgetAllocationSummary(
                budget_tokens=budget,
                tree_overhead_tokens=estimated_tree_overhead,
                net_code_budget=0,
                allocated_code_tokens=0,
                total_estimated_tokens=estimated_tree_overhead,
                objective_score=0.0,
            )
        total_full_cost = sum(self._effective_tier_cost(f, FidelityLevel.FULL) for f in files)
        if total_full_cost <= net_budget:
            for file_obj in files:
                file_obj.selected_fidelity = FidelityLevel.FULL
            return BudgetAllocationSummary(
                budget_tokens=budget,
                tree_overhead_tokens=estimated_tree_overhead,
                net_code_budget=net_budget,
                allocated_code_tokens=total_full_cost,
                total_estimated_tokens=estimated_tree_overhead + total_full_cost,
                objective_score=self._compute_total_objective(files),
            )
        used_tokens = self._greedy_marginal_allocation(files, net_budget)
        used_tokens = self._local_search_refinement(files, used_tokens, net_budget)
        used_tokens = self._fill_residual_budget(files, used_tokens, net_budget)
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
    def _file_tier_value(file_obj: FileAnalysis, level: FidelityLevel) -> float:
        weight = max(file_obj.pagerank_score, 1e-06)
        return weight * level.semantic_utility

    def _greedy_marginal_allocation(self, files: list[FileAnalysis], net_budget: int) -> int:
        used_tokens = 0
        while True:
            best_upgrade: _MarginalUpgrade | None = None
            for idx, file_obj in enumerate(files):
                cur_level = file_obj.selected_fidelity
                if cur_level == FidelityLevel.FULL:
                    continue
                cur_cost = self._effective_tier_cost(file_obj, cur_level)
                cur_val = self._file_tier_value(file_obj, cur_level)
                for cand_level in self._ORDERED_TIERS:
                    if cand_level <= cur_level:
                        continue
                    cand_cost = self._effective_tier_cost(file_obj, cand_level)
                    delta_tokens = cand_cost - cur_cost
                    if used_tokens + delta_tokens > net_budget:
                        continue
                    cand_val = self._file_tier_value(file_obj, cand_level)
                    delta_val = cand_val - cur_val
                    if delta_val <= 0.0:
                        continue
                    effective_divisor = max(delta_tokens, 1)
                    density = delta_val / effective_divisor
                    if best_upgrade is None or (density, delta_val, -delta_tokens) > (
                        best_upgrade.density,
                        best_upgrade.delta_utility,
                        -best_upgrade.delta_tokens,
                    ):
                        best_upgrade = _MarginalUpgrade(
                            file_idx=idx,
                            from_level=cur_level,
                            to_level=cand_level,
                            delta_utility=delta_val,
                            delta_tokens=delta_tokens,
                            density=density,
                        )
            if best_upgrade is None:
                break
            target_file = files[best_upgrade.file_idx]
            target_file.selected_fidelity = best_upgrade.to_level
            used_tokens += best_upgrade.delta_tokens
        return used_tokens

    def _local_search_refinement(
        self, files: list[FileAnalysis], used_tokens: int, net_budget: int
    ) -> int:
        max_iterations = 25
        for _ in range(max_iterations):
            improved = False
            downgrade_candidates = [
                (idx, f) for idx, f in enumerate(files) if f.selected_fidelity == FidelityLevel.FULL
            ]
            downgrade_candidates.sort(key=lambda item: item[1].pagerank_score)
            for down_idx, down_file in downgrade_candidates:
                cur_full_cost = self._effective_tier_cost(down_file, FidelityLevel.FULL)
                skel_cost = self._effective_tier_cost(down_file, FidelityLevel.SKELETON)
                freed_tokens = cur_full_cost - skel_cost
                if freed_tokens <= 0:
                    continue
                utility_loss = self._file_tier_value(
                    down_file, FidelityLevel.FULL
                ) - self._file_tier_value(down_file, FidelityLevel.SKELETON)
                available_if_downgraded = net_budget - used_tokens + freed_tokens
                best_up_idx = -1
                best_up_level = FidelityLevel.TREE
                best_up_gain = 0.0
                best_up_cost = 0
                for up_idx, up_file in enumerate(files):
                    if up_idx == down_idx:
                        continue
                    up_cur = up_file.selected_fidelity
                    if up_cur >= FidelityLevel.SKELETON:
                        continue
                    for target_tier in (FidelityLevel.SKELETON, FidelityLevel.SIGNATURES):
                        if target_tier <= up_cur:
                            continue
                        delta_c = self._effective_tier_cost(
                            up_file, target_tier
                        ) - self._effective_tier_cost(up_file, up_cur)
                        if delta_c <= available_if_downgraded:
                            gain = self._file_tier_value(
                                up_file, target_tier
                            ) - self._file_tier_value(up_file, up_cur)
                            if gain > utility_loss + 1e-06 and gain > best_up_gain:
                                best_up_idx = up_idx
                                best_up_level = target_tier
                                best_up_gain = gain
                                best_up_cost = delta_c
                if best_up_idx >= 0:
                    down_file.selected_fidelity = FidelityLevel.SKELETON
                    files[best_up_idx].selected_fidelity = best_up_level
                    used_tokens = used_tokens - freed_tokens + best_up_cost
                    improved = True
                    break
            if not improved:
                break
        return used_tokens

    def _fill_residual_budget(
        self, files: list[FileAnalysis], used_tokens: int, net_budget: int
    ) -> int:
        ranked_indices = sorted(
            range(len(files)), key=lambda i: files[i].pagerank_score, reverse=True
        )
        for idx in ranked_indices:
            file_obj = files[idx]
            cur_level = file_obj.selected_fidelity
            if cur_level == FidelityLevel.FULL:
                continue
            for next_level in reversed(self._ORDERED_TIERS):
                if next_level <= cur_level:
                    continue
                delta_c = self._effective_tier_cost(
                    file_obj, next_level
                ) - self._effective_tier_cost(file_obj, cur_level)
                if used_tokens + delta_c <= net_budget:
                    file_obj.selected_fidelity = next_level
                    used_tokens += delta_c
                    break
        return used_tokens

    @classmethod
    def _compute_total_objective(cls, files: list[FileAnalysis]) -> float:
        return sum(cls._file_tier_value(f, f.selected_fidelity) for f in files)
