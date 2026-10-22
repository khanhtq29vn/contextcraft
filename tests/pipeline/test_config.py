from __future__ import annotations

import pytest

from contextcraft import CompilationConfig, InvalidBudgetError


@pytest.mark.parametrize(
    "budget,expected",
    [
        ("16k", 16000),
        ("1.5M", 1500000),
        ("1.001k", 1001),
        ("1.000001m", 1000001),
        ("9007199254740993", 9007199254740993),
    ],
)
def test_budget_parsing_uses_exact_decimal_arithmetic(budget: str, expected: int) -> None:
    assert CompilationConfig.parse_budget(budget) == expected
    assert CompilationConfig(budget_tokens=budget).budget_tokens == expected


@pytest.mark.parametrize("budget", [0, -1, True, False, "bad", "0", "-2k", "0.0001k"])
def test_invalid_budgets_are_rejected(budget: str | int) -> None:
    with pytest.raises(InvalidBudgetError):
        CompilationConfig(budget_tokens=budget)


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
