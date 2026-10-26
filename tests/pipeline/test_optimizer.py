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
    mass = 40 ** (1 / 3)
    assert summary.objective_score == pytest.approx(0.6 * (0.82 * mass + 0.18))
    for file in files:
        for level in FidelityLevel:
            # Declarations scale with content mass; the bodies FULL adds do not.
            structure = min(level.semantic_utility, 0.82)
            expected = file.pagerank_score * (structure * mass + level.semantic_utility - structure)
            assert optimizer.tier_utility(file, level) == pytest.approx(expected)
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


def _tiered_file(path: str, rank: float, sigs: int, skel: int, full: int) -> FileAnalysis:
    costs = (0, sigs, skel, full)
    return FileAnalysis(
        path,
        path,
        "text",
        0,
        ParsedAst(source=b""),
        tiers={
            level: RenderedTier("", cost) for level, cost in zip(FidelityLevel, costs, strict=True)
        },
        pagerank_score=rank,
    )


def _allocate(files: list[FileAnalysis], budget: int) -> list[FileAnalysis]:
    TokenBudgetOptimizer(CompilationConfig(budget_tokens=budget)).optimize(
        files, tree_overhead_tokens=0
    )
    return files


def test_large_central_file_is_kept_before_tiny_low_rank_files() -> None:
    hub = _tiered_file("hub.py", 0.30, 2518, 6000, 12000)
    trivia = [_tiered_file(f"config/{index}.yaml", 0.005, 20, 40, 60) for index in range(30)]

    _allocate([hub, *trivia], 3000)

    assert hub.selected_fidelity == FidelityLevel.SIGNATURES
    assert all(file.selected_fidelity < FidelityLevel.FULL for file in trivia)


def test_central_go_files_are_not_dropped_for_low_rank_trivia() -> None:
    # Tier sizes and ranks measured on gin's context.go and gin.go.
    context = _tiered_file("context.go", 0.0913, 2601, 8103, 12346)
    gin = _tiered_file("gin.go", 0.0585, 1651, 3882, 7420)
    trivia = [_tiered_file(f"doc{index}.md", 0.002, 30, 45, 60) for index in range(60)]

    _allocate([context, gin, *trivia], 6000)

    assert context.selected_fidelity >= FidelityLevel.SIGNATURES
    assert gin.selected_fidelity >= FidelityLevel.SIGNATURES


@pytest.mark.parametrize(
    ("god", "modules", "count"),
    [
        ((0.25, 800, 3000, 12000), (0.025, 40, 120, 300), 30),
        ((0.6, 3000, 12000, 40000), (0.04, 200, 500, 1000), 10),
        # Realistic hub shapes, where SKEL keeps most of the source: gin's context.go
        # and flask's sansio/app.py, and the README's 10,000-token God class.
        ((0.25, 2601, 8103, 12346), (0.025, 150, 600, 1200), 25),
        ((0.15, 1079, 6255, 8705), (0.02, 200, 700, 1500), 20),
        ((0.46, 950, 3300, 10000), (0.023, 120, 445, 800), 20),
    ],
)
def test_god_object_never_takes_full_while_a_neighbour_lacks_a_skeleton(
    god: tuple[float, int, int, int], modules: tuple[float, int, int, int], count: int
) -> None:
    neighbours_full = count * (modules[3] + TokenBudgetOptimizer.FILE_WRAPPER_OVERHEAD_TOKENS)
    for budget in range(1000, god[3] + neighbours_full + 2000, 250):
        files = _allocate(
            [
                _tiered_file("god.py", *god),
                *(_tiered_file(f"m{index}.py", *modules) for index in range(count)),
            ],
            budget,
        )
        if files[0].selected_fidelity == FidelityLevel.FULL:
            assert min(file.selected_fidelity for file in files[1:]) >= FidelityLevel.SKELETON


def test_god_object_stays_elided_while_its_neighbours_get_full_source() -> None:
    files = _allocate(
        [
            _tiered_file("god.py", 0.25, 800, 3000, 12000),
            *(_tiered_file(f"m{index}.py", 0.025, 40, 120, 300) for index in range(30)),
        ],
        16000,
    )

    assert files[0].selected_fidelity == FidelityLevel.SKELETON
    assert all(file.selected_fidelity == FidelityLevel.FULL for file in files[1:])


@pytest.mark.parametrize("seed", range(30))
def test_lower_ranked_twin_never_gets_a_richer_tier(seed: int) -> None:
    rng = random.Random(seed)
    files = []
    for index in range(10):
        full = rng.randrange(40, 4000)
        sigs, skel = sorted(max(1, int(full * rng.uniform(0.05, 0.9))) for _ in range(2))
        rank = rng.uniform(0.01, 0.3)
        files.append(_tiered_file(f"a{index}", rank, sigs, skel, full))
        files.append(_tiered_file(f"b{index}", rank / 2, sigs, skel, full))
    budget = rng.randrange(200, sum(file.raw_tokens for file in files))

    _allocate(files, budget)

    for original, twin in zip(files[::2], files[1::2], strict=True):
        assert twin.selected_fidelity <= original.selected_fidelity


@pytest.mark.parametrize("output_format", ["markdown", "json", "xml"])
def test_central_module_survives_tiny_config_files_in_every_format(
    tmp_path: Path, output_format: str
) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "core.py").write_text(
        "".join(
            f"def operation_{index}(value: int, scale: int = {index}) -> int:\n"
            f'    """Apply operation {index} to the value."""\n'
            f"    result = value * scale + {index}\n"
            "    for step in range(3):\n"
            f"        result += step * {index}\n"
            "    return result\n\n"
            for index in range(60)
        )
    )
    imported = ", ".join(f"operation_{index}" for index in range(0, 60, 7))
    calls = "\n".join(f"    total += operation_{index}(total)" for index in range(0, 60, 7))
    for name in ("api", "cli", "jobs", "web"):
        (tmp_path / "app" / f"{name}.py").write_text(
            f"from app.core import {imported}\n\n\n"
            f"def run_{name}(total: int) -> int:\n{calls}\n    return total\n"
        )
    (tmp_path / "config").mkdir()
    for index in range(40):
        (tmp_path / "config" / f"service_{index}.yaml").write_text(
            f"name: service-{index}\nreplicas: {index % 3 + 1}\n"
        )

    result = ContextCraft(budget_tokens=2000, output_format=output_format).compile(tmp_path)
    fidelity = {file.rel_path: file.selected_fidelity for file in result.files}

    assert result.stats.compressed_tokens <= 2000
    assert fidelity["app/core.py"] >= FidelityLevel.SIGNATURES


def _allocate_with_pins(
    files: list[FileAnalysis], budget: int, pins: list[str]
) -> list[FileAnalysis]:
    config = CompilationConfig(budget_tokens=budget, pinned_full_files=pins)
    TokenBudgetOptimizer(config).optimize(files, tree_overhead_tokens=0)
    return files


def test_pinned_file_is_kept_full_and_the_rest_share_the_remainder() -> None:
    god = _tiered_file("legacy/god.py", 0.25, 800, 3000, 12000)
    modules = [_tiered_file(f"m{index}.py", 0.025, 40, 120, 300) for index in range(30)]

    files = _allocate_with_pins([god, *modules], 16000, ["legacy/"])

    assert god.selected_fidelity == FidelityLevel.FULL
    assert all(module.selected_fidelity >= FidelityLevel.SIGNATURES for module in modules)
    assert (
        sum(TokenBudgetOptimizer._effective_tier_cost(f, f.selected_fidelity) for f in files)
        <= 16000
    )


def test_pinned_files_are_raised_tier_by_tier_in_rank_order() -> None:
    def repository() -> list[FileAnalysis]:
        return [
            _tiered_file("low.py", 0.01, 100, 400, 900),
            _tiered_file("high.py", 0.02, 100, 400, 900),
            _tiered_file("hub.py", 0.9, 100, 500, 1000),
        ]

    # 1400 tokens fund both pins' signatures and skeletons but only one full source.
    low, high, hub = _allocate_with_pins(repository(), 1400, ["low.py", "high.py"])
    unpinned = {file.rel_path: file.selected_fidelity for file in _allocate(repository(), 1400)}

    assert high.selected_fidelity == FidelityLevel.FULL
    assert low.selected_fidelity == FidelityLevel.SKELETON
    assert hub.selected_fidelity == FidelityLevel.TREE
    # Without pins the central hub would take the budget instead.
    assert unpinned["hub.py"] == FidelityLevel.FULL
    assert unpinned["high.py"] < FidelityLevel.FULL


def test_no_pinned_file_is_dropped_while_another_pin_is_above_signatures() -> None:
    big = _tiered_file("big.py", 0.5, 300, 3000, 9000)
    small = _tiered_file("small.py", 0.1, 200, 400, 800)

    # Raising big.py to SKEL first would leave small.py out entirely.
    _allocate_with_pins([big, small], 3100, ["big.py", "small.py"])

    assert big.selected_fidelity == FidelityLevel.SIGNATURES
    assert small.selected_fidelity == FidelityLevel.FULL


def test_pinned_files_are_honoured_even_against_the_objective() -> None:
    peripheral = _tiered_file("peripheral.py", 0.001, 100, 200, 1000)
    hub = _tiered_file("hub.py", 0.5, 300, 600, 1000)

    _allocate_with_pins([peripheral, hub], 1100, ["peripheral.py"])

    assert peripheral.selected_fidelity == FidelityLevel.FULL
    assert hub.selected_fidelity == FidelityLevel.TREE
