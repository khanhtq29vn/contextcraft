from __future__ import annotations

import subprocess
import sys

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
        (" \t16K\r\n", 16000),
        (" 1.5 \tM ", 1500000),
        ("\u20031.5\u2003k\u2003", 1500),
        ("1.9", 1),
        ("00016k", 16000),
    ],
)
def test_budget_parsing_uses_exact_decimal_arithmetic(budget: str, expected: int) -> None:
    assert CompilationConfig.parse_budget(budget) == expected
    assert CompilationConfig(budget_tokens=budget).budget_tokens == expected


@pytest.mark.parametrize(
    "budget",
    [0, -1, True, False, "bad", "0", "-2k", "0.0001k", ".5k", "1.k", "1e3", "16kb", "1 6k"],
)
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


def test_budget_parsing_accepts_long_whitespace_around_a_suffix() -> None:
    budget = " " * 100_000 + "9" + " " * 100_000 + "k" + " " * 100_000

    assert CompilationConfig.parse_budget(budget) == 9000


def test_budget_parsing_rejects_adversarial_whitespace_without_backtracking() -> None:
    script = """
from contextcraft import CompilationConfig, InvalidBudgetError

for suffix in ("!", "k!", "m!"):
    try:
        CompilationConfig.parse_budget("9" + " " * 100_000 + suffix)
    except InvalidBudgetError:
        pass
    else:
        raise AssertionError("Invalid budget was accepted")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
