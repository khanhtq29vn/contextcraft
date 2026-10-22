from __future__ import annotations

from pathlib import Path

from benchmarks.run_benchmark import run_benchmark_suite


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
