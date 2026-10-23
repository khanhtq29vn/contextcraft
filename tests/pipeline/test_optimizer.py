from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

import pytest

from contextcraft import (
    CompilationConfig,
    ContextCraft,
    FidelityLevel,
)
from contextcraft.ast import ParsedAst
from contextcraft.ast.parser import parse
from contextcraft.elider import RenderedTier
from contextcraft.languages.builtin import PythonLanguage
from contextcraft.models import FileAnalysis
from contextcraft.optimizer import TokenBudgetOptimizer


def test_knapsack_assigns_higher_fidelity_to_higher_ranked_files(sample_repo: Path) -> None:
    """Under an intermediate budget, core auth modules should receive higher fidelity than leaf helpers."""
    cc = ContextCraft(budget_tokens=650, focus_query="JWT verify_token AuthConfig")
    result = cc.compile(sample_repo)

    fidelity_by_path = {f.rel_path: f.selected_fidelity for f in result.files}
    assert fidelity_by_path["src/auth/jwt_service.py"] >= fidelity_by_path["src/utils/helpers.py"]
    # At least one file should be elided or tree-only under a 650-token budget
    assert any(f.selected_fidelity < FidelityLevel.FULL for f in result.files)


def test_optimizer_prioritizes_ranked_fidelity_over_declaration_count() -> None:
    files = []
    for path, names, weight, signature_cost in (
        ("critical.py", ["critical"], 0.6, 10),
        ("api.py", ["first", "second", "third"], 0.4, 20),
    ):
        source = "".join(f"def {name}():\n    return 1\n" for name in names).encode()
        parsed = parse(source, PythonLanguage)
        signatures = "\n".join(
            parsed.text(symbol.signature_range) + " ..." for symbol in parsed.symbols
        )
        files.append(
            FileAnalysis(
                rel_path=path,
                abs_path="/" + path,
                language="python",
                size_bytes=len(source),
                parsed=parsed,
                pagerank_score=weight,
                tiers={
                    FidelityLevel.TREE: RenderedTier("", 0),
                    FidelityLevel.SIGNATURES: RenderedTier(signatures, signature_cost),
                    FidelityLevel.SKELETON: RenderedTier(signatures, 30),
                    FidelityLevel.FULL: RenderedTier(source.decode(), 40),
                },
            )
        )
    optimizer = TokenBudgetOptimizer(CompilationConfig(budget_tokens=70))
    summary = optimizer.optimize(files, tree_overhead_tokens=0)

    assert summary.allocated_code_tokens <= 70
    assert [file.selected_fidelity for file in files] == [FidelityLevel.FULL, FidelityLevel.TREE]
    assert summary.objective_score == 0.6
    for file in files:
        for level in FidelityLevel:
            assert (
                optimizer.tier_utility(file, level) == file.pagerank_score * level.semantic_utility
            )
    files[0].pagerank_score = 0
    assert optimizer.tier_utility(files[0], FidelityLevel.FULL) == 0


def test_allocation_is_repeatable_and_does_not_mutate_tiers_or_ast(tmp_path: Path) -> None:
    source = "".join(f"def operation_{index}():\n    return {index}\n" for index in range(50))
    (tmp_path / "api.py").write_bytes(source.encode("utf-8"))
    compiler = ContextCraft(budget_tokens=200)
    files = compiler.analyze_repository(tmp_path)
    optimizer = TokenBudgetOptimizer(compiler.config)
    tiers = dict(files[0].tiers)

    first = optimizer.optimize(files, tree_overhead_tokens=0)
    content = files[0].selected_content
    second = optimizer.optimize(files, tree_overhead_tokens=0)

    assert first.allocated_code_tokens == second.allocated_code_tokens <= 200
    assert files[0].selected_content == content
    assert files[0].selected_fidelity == FidelityLevel.TREE
    assert files[0].tiers == tiers
    assert len(files[0].symbols) == 50
    assert files[0].parsed.source == source.encode()


def test_local_refinement_trades_fidelity_for_higher_total_utility() -> None:
    files = []
    for path, names, costs, selected in (
        ("implementation.py", ["run"], (0, 10, 70, 200), FidelityLevel.SKELETON),
        ("api.py", ["other"], (0, 40, 80, 200), FidelityLevel.TREE),
    ):
        source = "".join(f"def {name}(): return 1\n" for name in names).encode()
        parsed = parse(source, PythonLanguage)
        files.append(
            FileAnalysis(
                path,
                path,
                "python",
                len(source),
                parsed,
                tiers={
                    level: RenderedTier(
                        "" if level == FidelityLevel.TREE else source.decode(), cost
                    )
                    for level, cost in zip(FidelityLevel, costs, strict=True)
                },
                pagerank_score=0.5,
                selected_fidelity=selected,
            )
        )
    optimizer = TokenBudgetOptimizer()

    used = optimizer._local_search_refinement(files, used_tokens=88, net_budget=90)

    assert used <= 90
    assert all(file.selected_fidelity == FidelityLevel.SIGNATURES for file in files)


@pytest.mark.parametrize("seed", range(50))
def test_indexed_refinement_matches_exhaustive_search(seed: int) -> None:
    rng = random.Random(seed)
    files = []
    for index in range(12):
        costs = [0, *sorted(rng.choices(range(10, 100, 10), k=3))]
        files.append(
            FileAnalysis(
                str(index),
                str(index),
                "text",
                0,
                ParsedAst(source=b""),
                tiers={
                    level: RenderedTier("", cost)
                    for level, cost in zip(FidelityLevel, costs, strict=True)
                },
                pagerank_score=rng.choice([0.0, 0.1, 0.2, 0.3]),
                selected_fidelity=rng.choice(list(FidelityLevel)),
            )
        )
    expected = [replace(file) for file in files]
    optimizer = TokenBudgetOptimizer()
    used = sum(optimizer._effective_tier_cost(file, file.selected_fidelity) for file in files)
    budget = used + rng.randrange(50)
    actual_used = optimizer._local_search_refinement(files, used, budget)

    # Keep an exhaustive oracle to verify affordability, exclusions, and tie order.
    for _ in range(25):
        best_gain = 1e-6
        best_swap = None
        for down_index, down in enumerate(expected):
            current_cost = optimizer._effective_tier_cost(down, down.selected_fidelity)
            current_value = optimizer.tier_utility(down, down.selected_fidelity)
            for down_level in FidelityLevel:
                if down_level >= down.selected_fidelity:
                    continue
                freed = current_cost - optimizer._effective_tier_cost(down, down_level)
                if freed <= 0:
                    continue
                loss = current_value - optimizer.tier_utility(down, down_level)
                for up_index, up in enumerate(expected):
                    if up_index == down_index:
                        continue
                    for target in FidelityLevel:
                        if target <= up.selected_fidelity:
                            continue
                        cost = optimizer._effective_tier_cost(
                            up, target
                        ) - optimizer._effective_tier_cost(up, up.selected_fidelity)
                        gain = (
                            optimizer.tier_utility(up, target)
                            - optimizer.tier_utility(up, up.selected_fidelity)
                            - loss
                        )
                        if cost <= budget - used + freed and gain > best_gain:
                            best_gain = gain
                            best_swap = down_index, down_level, up_index, target, cost - freed
        if best_swap is None:
            break
        down_index, down_level, up_index, target, delta = best_swap
        expected[down_index].selected_fidelity = down_level
        expected[up_index].selected_fidelity = target
        used += delta

    assert actual_used == used <= budget
    assert [file.selected_fidelity for file in files] == [
        file.selected_fidelity for file in expected
    ]
