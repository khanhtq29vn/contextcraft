from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from benchmarks.run_benchmark import (
    evaluate_contextcraft,
    evaluate_naive_truncation,
    run_benchmark_suite,
)
from contextcraft import ContextCraft, FidelityLevel, RenderedTier, TokenCounter


def test_benchmark_uses_current_analysis_and_fidelity_models(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        "class Service:\n"
        "    def run(self, value):\n"
        "        return value + 1\n\n"
        "def _private_helper():\n"
        "    return 0\n",
        encoding="utf-8",
    )
    markdown, latex = run_benchmark_suite(tmp_path, [512], focus_query="Service")

    assert "Naive Truncation" in markdown
    assert "ContextCraft (Ours)" in markdown
    assert "YES" in markdown
    assert "512" in markdown
    assert "\\begin{table}" in latex
    assert "ContextCraft (Ours)" in latex


def test_naive_benchmark_stops_before_the_first_file_that_does_not_fit(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.py").write_text(f"def {name}(): return 1\n")
    files = ContextCraft().analyze_repository(tmp_path)
    for file, tokens in zip(files, (10, 100, 1), strict=True):
        file.tiers[FidelityLevel.FULL] = RenderedTier(file.parsed.source.decode(), tokens)

    row = evaluate_naive_truncation(files, 50, {file.rel_path for file in files}, TokenCounter())

    assert row.emitted_tokens == 50
    assert row.core_symbol_retention_pct == 33.3
    assert row.public_signature_coverage_pct == 33.3
    assert row.fits_budget


def test_contextcraft_benchmark_estimates_retention_from_fidelity_tiers(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def public_a(): return 1\ndef _private(): return 2\n")
    (tmp_path / "b.py").write_text("def public_b(): return 1\n")
    (tmp_path / "c.py").write_text("def public_c(): return 1\n")
    result = ContextCraft().compile(tmp_path)
    for file, level in zip(
        result.files,
        (FidelityLevel.SIGNATURES, FidelityLevel.SKELETON, FidelityLevel.TREE),
        strict=True,
    ):
        file.selected_fidelity = level
        if level != FidelityLevel.TREE:
            file.tiers[level] = RenderedTier("# no signatures", 3)

    with patch("benchmarks.run_benchmark.ContextCraft.compile", return_value=result):
        row = evaluate_contextcraft(tmp_path, 512, None, {"a.py", "b.py", "c.py"})

    assert row.public_signature_coverage_pct == 66.7
    assert row.core_symbol_retention_pct == 25.0


def test_benchmark_and_sdk_report_the_same_signature_coverage(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Project\n## Usage\n")
    (tmp_path / "config.json").write_text('{"key": "value"}')
    (tmp_path / "api.py").write_text(
        "".join(
            f"def operation_{index}(value: int) -> int:\n    return value + {index}\n"
            for index in range(50)
        )
    )

    result = ContextCraft(budget_tokens=350).compile(tmp_path)
    row = evaluate_contextcraft(tmp_path, 350, None, {"api.py"})

    assert 0 < result.stats.preserved_signatures_pct < 100
    assert row.public_signature_coverage_pct == round(result.stats.preserved_signatures_pct, 1)
    assert row.emitted_tokens == result.stats.compressed_tokens
