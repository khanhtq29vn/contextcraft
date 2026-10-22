from __future__ import annotations

from pathlib import Path

from contextcraft import (
    CompilationConfig,
    ContextCraft,
    FidelityLevel,
)
from contextcraft.ast import ParsedAst
from contextcraft.elider import RenderedTier
from contextcraft.models import FileAnalysis
from contextcraft.optimizer import TokenBudgetOptimizer


def test_optimizer_assigns_fidelity_within_estimated_budget() -> None:
    files = [
        FileAnalysis(
            rel_path=name,
            abs_path="/" + name,
            language="text",
            size_bytes=40,
            parsed=ParsedAst(source=b"x" * 40),
            pagerank_score=weight,
            tiers={
                level: RenderedTier("x" * cost, cost)
                for level, cost in zip(FidelityLevel, (0, 10, 20, 40), strict=True)
            },
        )
        for name, weight in (("high.txt", 0.9), ("low.txt", 0.1))
    ]
    summary = TokenBudgetOptimizer(CompilationConfig(budget_tokens=60)).optimize(
        files, tree_overhead_tokens=0
    )

    assert summary.allocated_code_tokens <= 60
    assert files[0].selected_fidelity > files[1].selected_fidelity
    assert summary.objective_score > 0


def test_knapsack_assigns_higher_fidelity_to_higher_ranked_files(sample_repo: Path) -> None:
    """Under an intermediate budget, core auth modules should receive higher fidelity than leaf helpers."""
    cc = ContextCraft(budget_tokens=650, focus_query="JWT verify_token AuthConfig")
    result = cc.compile(sample_repo)

    fidelity_by_path = {f.rel_path: f.selected_fidelity for f in result.files}
    assert fidelity_by_path["src/auth/jwt_service.py"] >= fidelity_by_path["src/utils/helpers.py"]
    # At least one file should be elided or tree-only under a 650-token budget
    assert any(f.selected_fidelity < FidelityLevel.FULL for f in result.files)
