"""Unit tests for `DependencyGraphScorer` and `TokenBudgetOptimizer`."""

from __future__ import annotations

from pathlib import Path

import pytest

from contextcraft.core import ContextCraft
from contextcraft.models import CompilationConfig, FidelityLevel, InvalidBudgetError


def test_pagerank_ranks_core_dependencies_above_leaf_utilities(sample_repo: Path) -> None:
    """Verify `src/auth/models.py` and `src/auth/jwt_service.py` outrank `src/utils/helpers.py`."""
    cc = ContextCraft()
    analyses = cc.analyze_repository(sample_repo)

    pr_by_path = {f.rel_path: f.pagerank_score for f in analyses}
    total_pr = sum(pr_by_path.values())

    assert abs(total_pr - 1.0) < 1e-5
    assert pr_by_path["src/auth/models.py"] > pr_by_path["src/utils/helpers.py"]
    assert pr_by_path["src/auth/jwt_service.py"] > pr_by_path["src/utils/helpers.py"]


def test_personalized_pagerank_focus_query_and_focus_files(sample_repo: Path) -> None:
    """Verify `focus_query` and `focus_files` shift PageRank centrality toward target modules."""
    cc = ContextCraft()

    baseline = {f.rel_path: f.pagerank_score for f in cc.analyze_repository(sample_repo)}
    focused_jwt = {
        f.rel_path: f.pagerank_score
        for f in cc.analyze_repository(
            sample_repo,
            focus_query="JWT verify_token revocation hmac",
        )
    }
    assert focused_jwt["src/auth/jwt_service.py"] > baseline["src/auth/jwt_service.py"]

    focused_leaf = {
        f.rel_path: f.pagerank_score
        for f in cc.analyze_repository(
            sample_repo,
            focus_files=["src/utils/helpers.py"],
        )
    }
    assert focused_leaf["src/utils/helpers.py"] > baseline["src/utils/helpers.py"] * 2.0


@pytest.mark.parametrize("budget", [180, 450, 800, 1400, 5000])
def test_knapsack_optimizer_strictly_respects_all_token_budgets(
    sample_repo: Path,
    budget: int,
) -> None:
    """Verify compiled output never exceeds `budget_tokens` across tight and generous budgets."""
    cc = ContextCraft(budget_tokens=budget, focus_query="JWT verify_token")
    result = cc.compile(sample_repo)

    assert result.stats.compressed_tokens <= budget
    assert result.stats.budget_tokens == budget


def test_knapsack_assigns_higher_fidelity_to_higher_ranked_files(sample_repo: Path) -> None:
    """Under an intermediate budget, core auth modules should receive higher fidelity than leaf helpers."""
    cc = ContextCraft(budget_tokens=650, focus_query="JWT verify_token AuthConfig")
    result = cc.compile(sample_repo)

    fidelity_by_path = {f.rel_path: f.selected_fidelity for f in result.files}
    assert (
        fidelity_by_path["src/auth/jwt_service.py"]
        >= fidelity_by_path["src/utils/helpers.py"]
    )
    # At least one file should be elided or tree-only under a 650-token budget
    assert any(f.selected_fidelity < FidelityLevel.FULL_SOURCE for f in result.files)


def test_budget_shorthand_parsing_and_validation() -> None:
    """Verify `CompilationConfig.parse_budget` supports shorthand and rejects invalid values."""
    assert CompilationConfig.parse_budget("16k") == 16_000
    assert CompilationConfig.parse_budget("1.5M") == 1_500_000
    assert CompilationConfig.parse_budget(4096) == 4096

    with pytest.raises(InvalidBudgetError):
        CompilationConfig.parse_budget("-5k")

    with pytest.raises(InvalidBudgetError):
        CompilationConfig.parse_budget("0")

    with pytest.raises(InvalidBudgetError):
        CompilationConfig.parse_budget("not-a-number")
