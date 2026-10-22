"""Rich CLI interface for ContextCraft.

Provides a fast, zero-config command-line interface:
    contextcraft . --budget 32k --focus "authentication flow" -o context.md
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from contextcraft import __version__
from contextcraft.core import ContextCraft
from contextcraft.models import (
    CompilationResult,
    ContextCraftError,
    FidelityLevel,
    OutputFormat,
)

app = typer.Typer(
    name="contextcraft",
    help=(
        "AST-Aware, Dependency-Graph-Ranked, Token-Budgeted "
        "Semantic Codebase Compressor for LLMs."
    ),
    add_completion=False,
    no_args_is_help=False,
)

err_console = Console(stderr=True)
out_console = Console(stderr=False)


def _version_callback(value: bool) -> None:
    if value:
        out_console.print(f"contextcraft {__version__}")
        raise typer.Exit(code=0)


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the target Git repository or source directory.",
            show_default=True,
        ),
    ] = Path("."),
    budget: Annotated[
        str,
        typer.Option(
            "--budget",
            "-b",
            help="Strict token budget (supports shorthand like '16k', '32k', '128k', or '8000').",
            show_default=True,
        ),
    ] = "32k",
    encoding: Annotated[
        str,
        typer.Option(
            "--encoding",
            "-enc",
            help="Tiktoken encoding name used for token accounting (e.g. cl100k_base, o200k_base).",
            show_default=True,
        ),
    ] = "cl100k_base",
    focus: Annotated[
        str | None,
        typer.Option(
            "--focus",
            "-f",
            help="Natural-language query or symbol keywords to bias Personalized PageRank.",
        ),
    ] = None,
    focus_file: Annotated[
        list[str] | None,
        typer.Option(
            "--focus-file",
            help="Specific relative file path or glob to boost in PageRank (repeatable).",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-m",
            case_sensitive=False,
            help="Target output format: markdown, xml (Claude-optimized), or json.",
            show_default=True,
        ),
    ] = OutputFormat.MARKDOWN,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write compiled context to this file path instead of stdout.",
        ),
    ] = None,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include",
            "-i",
            help="Glob pattern of files to include (repeatable).",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-e",
            help="Additional glob pattern of files to exclude (repeatable).",
        ),
    ] = None,
    copy: Annotated[
        bool,
        typer.Option(
            "--copy",
            "-c",
            help="Copy the compiled output directly to the system clipboard.",
        ),
    ] = False,
    no_redact: Annotated[
        bool,
        typer.Option(
            "--no-redact",
            help="Disable automatic secret and API key redaction.",
        ),
    ] = False,
    no_gitignore: Annotated[
        bool,
        typer.Option(
            "--no-gitignore",
            help="Do not respect .gitignore and .contextignore files.",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress the Rich telemetry summary table on stderr.",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show ContextCraft version and exit.",
        ),
    ] = False,
) -> None:
    """Compile a repository into an optimal, token-budgeted LLM context artifact."""
    _ = version
    try:
        exclude_list = list(exclude) if exclude else []
        if output is not None:
            # Ensure we never accidentally ingest the output file being written
            exclude_list.append(output.name)

        compiler = ContextCraft(
            budget_tokens=budget,
            focus_query=focus,
            focus_files=list(focus_file) if focus_file else [],
            output_format=output_format,
            include_patterns=list(include) if include else [],
            exclude_patterns=exclude_list,
            respect_gitignore=not no_gitignore,
            redact_secrets=not no_redact,
            tokenizer_encoding=encoding,
        )
        result = compiler.compile(path)
    except ContextCraftError as exc:
        err_console.print(f"[bold red]ContextCraft Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # pragma: no cover
        err_console.print(f"[bold red]Unexpected Failure:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    # 1. Emit artifact to file or stdout
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.content, encoding="utf-8")
    else:
        sys.stdout.write(result.content)
        if not result.content.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()

    # 2. Optionally copy to clipboard
    copied_ok = False
    if copy:
        copied_ok = _copy_to_clipboard(result.content)

    # 3. Render telemetry dashboard to stderr unless --quiet is set
    if not quiet:
        _render_telemetry_summary(
            result=result,
            output_path=output,
            copied_to_clipboard=copied_ok,
            copy_requested=copy,
        )


def _render_telemetry_summary(
    *,
    result: CompilationResult,
    output_path: Path | None,
    copied_to_clipboard: bool,
    copy_requested: bool,
) -> None:
    """Render a compact Rich telemetry table to `stderr`."""
    stats = result.stats

    metrics_table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    metrics_table.add_column("Metric", style="bold white")
    metrics_table.add_column("Value", justify="right", style="green")

    metrics_table.add_row("Repository Root", result.root_path)
    metrics_table.add_row(
        "Files Compiled",
        f"{stats.files_compiled} (skipped {stats.ignored_files_skipped} ignored, {stats.binary_files_skipped} binary)",
    )
    metrics_table.add_row("Raw Repository Tokens", f"{stats.raw_tokens:,}")
    metrics_table.add_row(
        "Compressed Tokens",
        f"{stats.compressed_tokens:,} / {stats.budget_tokens:,} ({stats.budget_utilization_pct:.1f}%)",
    )
    metrics_table.add_row(
        "Compression Ratio",
        f"{stats.compression_ratio:.2f}x ({stats.token_savings_pct:.1f}% saved)",
    )
    metrics_table.add_row(
        "Fidelity Allocation",
        (
            f"FULL: {stats.fidelity_counts.get('FULL', 0)} | "
            f"SKEL: {stats.fidelity_counts.get('SKEL', 0)} | "
            f"SIGS: {stats.fidelity_counts.get('SIGS', 0)} | "
            f"TREE: {stats.fidelity_counts.get('TREE', 0)}"
        ),
    )
    metrics_table.add_row(
        "Signature Coverage",
        f"{stats.preserved_signatures_pct:.1f}% ({stats.total_symbols_extracted} AST symbols)",
    )
    if stats.secrets_redacted > 0:
        metrics_table.add_row(
            "Secrets Scrubbed",
            f"[bold yellow]{stats.secrets_redacted} redacted[/bold yellow]",
        )
    metrics_table.add_row("Execution Time", f"{stats.execution_time_ms:.1f} ms")

    if output_path is not None:
        metrics_table.add_row("Saved Output", str(output_path))
    if copy_requested:
        status_str = "Copied to clipboard" if copied_to_clipboard else "Clipboard unavailable"
        metrics_table.add_row("Clipboard", status_str)

    err_console.print()
    err_console.print(
        Panel.fit(
            metrics_table,
            title="[bold magenta]ContextCraft Compilation Summary[/bold magenta]",
            border_style="bright_blue",
        )
    )

    # Display top-ranked files table if files were compiled
    if result.files:
        top_table = Table(
            title="Top Architectural Files by Personalized PageRank",
            box=box.SIMPLE_HEAD,
            header_style="bold blue",
        )
        top_table.add_column("File Path", style="white")
        top_table.add_column("Fidelity", justify="center")
        top_table.add_column("PageRank", justify="right", style="cyan")
        top_table.add_column("Tokens (Selected / Raw)", justify="right", style="green")

        badge_styles = {
            FidelityLevel.FULL_SOURCE: "[bold green]FULL[/bold green]",
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: "[bold cyan]SKEL[/bold cyan]",
            FidelityLevel.SIGNATURES_ONLY: "[bold yellow]SIGS[/bold yellow]",
            FidelityLevel.TREE_ONLY: "[dim]TREE[/dim]",
        }

        ranked = sorted(result.files, key=lambda f: (-f.pagerank_score, f.rel_path))
        for file_obj in ranked[:5]:
            top_table.add_row(
                file_obj.rel_path,
                badge_styles[file_obj.selected_fidelity],
                f"{file_obj.pagerank_score * 100.0:.1f}%",
                f"{file_obj.selected_tokens:,} / {file_obj.raw_tokens:,}",
            )
        err_console.print(top_table)


def _copy_to_clipboard(text: str) -> bool:
    """Copy `text` to the system clipboard using native OS utilities."""
    commands: list[list[str]] = [
        ["pbcopy"],
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["clip"],
    ]
    for cmd in commands:
        executable = shutil.which(cmd[0])
        if executable is None:
            continue
        try:
            subprocess.run(
                [executable, *cmd[1:]],
                input=text.encode("utf-8"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            return True
        except Exception:
            continue
    return False


if __name__ == "__main__":  # pragma: no cover
    app()
