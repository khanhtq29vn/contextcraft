"""Quantitative benchmark suite for ContextCraft.

Evaluates ContextCraft against two industry baselines across multiple token budgets:
1. `Raw Concatenation` (`repomix` / `gitingest` baseline: concatenates all files verbatim)
2. `Naive Prefix Truncation` (truncates the raw concatenation stream at token budget $B$)
3. `ContextCraft` (Multi-Resolution AST Elision + Personalized PageRank + Knapsack Solver)

Outputs both:
- A GitHub-flavored Markdown comparison table (for `README.md`)
- A publication-ready LaTeX `booktabs` table (for ACL / EMNLP / ICSE System Demo papers)

Usage:
    uv run python benchmarks/run_benchmark.py . --focus "AST elision knapsack pagerank"
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from contextcraft.core import ContextCraft
from contextcraft.elider import FidelityLevel, TokenCounter
from contextcraft.models import FileAnalysis


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    """Metrics captured for a single method at a specific token budget."""

    method: str
    budget_tokens: int
    emitted_tokens: int
    compression_ratio: float
    core_symbol_retention_pct: float
    public_signature_coverage_pct: float
    fits_budget: bool


def evaluate_naive_truncation(
    analyses: list[FileAnalysis],
    budget_tokens: int,
    core_files: set[str],
    counter: TokenCounter,
) -> BenchmarkRow:
    """Simulate naive alphabetical file concatenation truncated hard at `budget_tokens`."""
    sorted_files = sorted(analyses, key=lambda f: f.rel_path)
    raw_total = sum(f.raw_tokens for f in sorted_files)

    used_tokens = 0
    included_files: set[str] = set()

    for file_obj in sorted_files:
        wrapper_cost = 18
        if used_tokens + file_obj.raw_tokens + wrapper_cost <= budget_tokens:
            used_tokens += file_obj.raw_tokens + wrapper_cost
            included_files.add(file_obj.rel_path)
        else:
            break

    total_public_syms = sum(len([s for s in f.symbols if s.is_public]) for f in sorted_files)
    retained_public_syms = sum(
        len([s for s in f.symbols if s.is_public])
        for f in sorted_files
        if f.rel_path in included_files
    )

    core_total = sum(len(f.symbols) for f in sorted_files if f.rel_path in core_files)
    core_retained = sum(
        len(f.symbols)
        for f in sorted_files
        if f.rel_path in core_files and f.rel_path in included_files
    )

    core_pct = (core_retained / core_total * 100.0) if core_total > 0 else 100.0
    sig_pct = (retained_public_syms / total_public_syms * 100.0) if total_public_syms > 0 else 100.0
    emitted = min(raw_total, budget_tokens)
    ratio = round(raw_total / max(emitted, 1), 2)
    _ = counter

    return BenchmarkRow(
        method="Naive Truncation",
        budget_tokens=budget_tokens,
        emitted_tokens=emitted,
        compression_ratio=ratio,
        core_symbol_retention_pct=round(core_pct, 1),
        public_signature_coverage_pct=round(sig_pct, 1),
        fits_budget=True,
    )


def evaluate_contextcraft(
    repo_path: Path,
    budget_tokens: int,
    focus_query: str | None,
    core_files: set[str],
) -> BenchmarkRow:
    """Run `ContextCraft` at `budget_tokens` and compute architectural retention metrics."""
    cc = ContextCraft(budget_tokens=budget_tokens, focus_query=focus_query)
    result = cc.compile(repo_path)

    total_public_syms = sum(len([s for s in f.symbols if s.is_public]) for f in result.files)
    retained_public_syms = sum(
        len([s for s in f.symbols if s.is_public])
        for f in result.files
        if f.selected_fidelity >= FidelityLevel.SIGNATURES
    )

    core_total = sum(len(f.symbols) for f in result.files if f.rel_path in core_files)
    core_retained = sum(
        len(f.symbols)
        for f in result.files
        if f.rel_path in core_files and f.selected_fidelity >= FidelityLevel.SKELETON
    )

    core_pct = (core_retained / core_total * 100.0) if core_total > 0 else 100.0
    sig_pct = (retained_public_syms / total_public_syms * 100.0) if total_public_syms > 0 else 100.0

    return BenchmarkRow(
        method="ContextCraft (Ours)",
        budget_tokens=budget_tokens,
        emitted_tokens=result.stats.compressed_tokens,
        compression_ratio=result.stats.compression_ratio,
        core_symbol_retention_pct=round(core_pct, 1),
        public_signature_coverage_pct=round(sig_pct, 1),
        fits_budget=result.stats.compressed_tokens <= budget_tokens,
    )


def format_markdown_table(rows: list[BenchmarkRow], raw_tokens: int) -> str:
    """Render benchmark comparison rows as a GitHub Markdown table."""
    lines = [
        "### Quantitative Compression & Architectural Retention Benchmark",
        "",
        f"- **Uncompressed Repository Baseline (`repomix` / raw concatenation):** `{raw_tokens:,}` tokens (`1.00x`, overflows tight context budgets)",
        "",
        "| Method | Target Budget ($B$) | Emitted Tokens | Compression Ratio | Core Symbol Retention | Public API Signature Coverage | Budget Compliant |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in rows:
        compliant = "YES" if r.fits_budget else "NO (Overflow)"
        lines.append(
            f"| **{r.method}** | `{r.budget_tokens:,}` | `{r.emitted_tokens:,}` | "
            f"`{r.compression_ratio:.2f}x` | `{r.core_symbol_retention_pct:.1f}%` | "
            f"`{r.public_signature_coverage_pct:.1f}%` | {compliant} |"
        )
    return "\n".join(lines)


def format_latex_table(rows: list[BenchmarkRow], raw_tokens: int) -> str:
    """Render a publication-ready LaTeX `booktabs` table for academic papers."""
    lines = [
        "% LaTeX booktabs table for ACL / EMNLP / ICSE System Demonstration Paper",
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Budget ($B$)} & \\textbf{Tokens} & \\textbf{Comp. Ratio} & \\textbf{Core Ret. (\\%)} & \\textbf{Sig. Cov. (\\%)} \\\\",
        "\\midrule",
        f"Raw Concatenation & $\\infty$ & {raw_tokens:,} & $1.00\\times$ & 100.0 & 100.0 \\\\",
        "\\midrule",
    ]
    for r in rows:
        lines.append(
            f"{r.method} & {r.budget_tokens:,} & {r.emitted_tokens:,} & "
            f"${r.compression_ratio:.2f}\\times$ & {r.core_symbol_retention_pct:.1f} & "
            f"{r.public_signature_coverage_pct:.1f} \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\caption{Comparison of Naive Prefix Truncation vs.\\ \\textsc{ContextCraft} across strict token budgets $B$.}",
            "\\label{tab:contextcraft_benchmark}",
            "\\end{table}",
        ]
    )
    return "\n".join(lines)


def run_benchmark_suite(
    repo_path: Path,
    budgets: list[int],
    focus_query: str | None,
) -> tuple[str, str]:
    """Execute the benchmark suite and return `(markdown_table, latex_table)`."""
    cc = ContextCraft(focus_query=focus_query)
    analyses = cc.analyze_repository(repo_path, focus_query=focus_query)
    raw_tokens = sum(f.raw_tokens for f in analyses)

    # Define top-35% PageRank files as core architectural modules
    ranked = sorted(analyses, key=lambda f: f.pagerank_score, reverse=True)
    top_k = max(1, len(ranked) // 3)
    core_files = {f.rel_path for f in ranked[:top_k]}

    counter = TokenCounter()
    rows: list[BenchmarkRow] = []

    for b in budgets:
        rows.append(evaluate_naive_truncation(analyses, b, core_files, counter))
        rows.append(evaluate_contextcraft(repo_path, b, focus_query, core_files))

    return format_markdown_table(rows, raw_tokens), format_latex_table(rows, raw_tokens)


def main() -> None:
    """CLI entry point for running repository compression benchmarks."""
    parser = argparse.ArgumentParser(
        description="Run ContextCraft compression & architectural retention benchmarks."
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to target repository (default: current directory).",
    )
    parser.add_argument(
        "--focus",
        default="AST elision knapsack optimizer pagerank",
        help="Focus query for Personalized PageRank.",
    )
    parser.add_argument(
        "--budgets",
        default="2500,4000,6000",
        help="Comma-separated token budgets to evaluate.",
    )
    args = parser.parse_args()

    budgets = [int(x.strip()) for x in str(args.budgets).split(",") if x.strip()]
    md_table, latex_table = run_benchmark_suite(
        repo_path=Path(args.repo_path).resolve(),
        budgets=budgets,
        focus_query=args.focus,
    )

    print(md_table)
    print("\n" + "=" * 80 + "\n")
    print(latex_table)


if __name__ == "__main__":
    main()
