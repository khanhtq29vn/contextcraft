"""Cyclopts commands and Rich output for the optional CLI extra."""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Annotated

from cyclopts import App, Group, Parameter, Token
from cyclopts.help import ColumnSpec, DefaultFormatter, PanelSpec, TableSpec
from cyclopts.help.specs import DescriptionRenderer, NameRenderer
from cyclopts.validators import Number
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.pretty import Pretty
from rich.table import Table

from . import (
    Config,
    ContextCraft,
    FidelityLevel,
    OutputFormat,
    RepositoryAnalysis,
    TokenCounter,
    TokenizerEncoding,
    __version__,
)

_DEFAULTS = Config()
_LEVELS = (
    FidelityLevel.TREE,
    FidelityLevel.SIGS,
    FidelityLevel.SKEL,
    FidelityLevel.FULL,
)
_FORMATS = {
    value.as_str(): value
    for value in (OutputFormat.MARKDOWN, OutputFormat.XML, OutputFormat.JSON)
}
_ENCODINGS = {
    value.as_str(): value
    for value in (
        TokenizerEncoding.GPT2,
        TokenizerEncoding.R50K_BASE,
        TokenizerEncoding.P50K_BASE,
        TokenizerEncoding.P50K_EDIT,
        TokenizerEncoding.CL100K_BASE,
        TokenizerEncoding.O200K_BASE,
        TokenizerEncoding.O200K_HARMONY,
    )
}

INPUT_GROUP = Group("Input", sort_key=0)
OUTPUT_GROUP = Group("Output", sort_key=1)
FOCUS_GROUP = Group("Focus", sort_key=2)
TOKEN_GROUP = Group("Token accounting", sort_key=3)
DIAGNOSTICS_GROUP = Group("Diagnostics", sort_key=4)
GENERAL_GROUP = Group("General", sort_key=5)

stderr = Console(stderr=True, markup=False, highlight=False)
app = App(
    name="contextcraft",
    help="AST-Aware, Personalized-PageRank-Ranked, Token-Budgeted Codebase Compressor for LLMs",
    error_console=stderr,
    error_formatter=str,
    help_formatter=DefaultFormatter(
        panel_spec=PanelSpec(box=box.SIMPLE, padding=(1, 0)),
        table_spec=TableSpec(box=None, show_header=False, padding=(0, 2)),
        column_specs=(
            ColumnSpec(
                renderer=NameRenderer(), header="Option", width=28, overflow="fold"
            ),
            ColumnSpec(
                renderer=DescriptionRenderer(), header="Description", overflow="fold"
            ),
        ),
    ),
    group_arguments=INPUT_GROUP,
    group_commands=GENERAL_GROUP,
    version=__version__,
    version_flags=("--version", "-V"),
)


def _parse_budget(_: type[int], tokens: Sequence[Token]) -> int:
    match = re.fullmatch(r"([0-9]+)([kKmM]?)", tokens[0].value.strip())
    if match is None:
        raise ValueError(
            "budget must be a positive integer, optionally suffixed with k or m"
        )
    number, suffix = match.groups()
    budget = int(number) * {"": 1, "k": 1_000, "m": 1_000_000}[suffix.lower()]
    if budget == 0:
        raise ValueError("budget must be positive")
    return budget


def _write_output(content: str, output: Path | None, *, render_markdown: bool) -> None:
    if output is not None:
        with output.open("w", encoding="utf-8", newline="") as stream:
            stream.write(content)
    elif render_markdown and sys.stdout.isatty():
        Console().print(Markdown(content))
    else:
        binary_stdout = getattr(sys.stdout, "buffer", None)
        if binary_stdout is not None:
            binary_stdout.write(content.encode("utf-8"))
            binary_stdout.flush()
        else:
            sys.stdout.write(content)
            sys.stdout.flush()


def _render_summary(
    analysis: RepositoryAnalysis,
    config: Config,
    elapsed_ms: float,
    output: Path | None,
) -> None:
    index = analysis.index
    files = index.files
    tiers = {
        file_id: file_tiers.levels
        for file_id, file_tiers in analysis.tiers.files.items()
    }
    scores = analysis.scores
    artifact = analysis.artifact
    selected = artifact.selected_tiers
    counter = TokenCounter(config.tokenizer_encoding, config.allow_token_estimates)
    # Unselected framed costs may be estimates. Count source text for these metrics.
    full_counts = counter.count_full_sources(analysis.tiers, config.enable_parallel)
    full_tokens = sum(full_counts.values())
    counts = Counter(selected.values())
    loaded_count = len(analysis.repository.sources)
    metrics = [
        ("Repository", str(index.root)),
        ("Indexed / loaded files", f"{len(files)} / {loaded_count}"),
        ("Skipped sources", str(len(files) - loaded_count)),
        ("Encoding", config.tokenizer_encoding.as_str()),
        ("Full-source tokens", f"{full_tokens:,}"),
        (
            "Output tokens / budget",
            (
                f"{artifact.tokens:,} / {config.budget_tokens:,} "
                f"({100 * artifact.tokens / config.budget_tokens:.1f}%)"
            ),
        ),
        (
            "Token counts",
            "Estimated (no exact budget guarantee)"
            if artifact.token_counts_estimated
            else "Exact",
        ),
    ]
    if full_tokens and artifact.tokens:
        metrics.append(
            (
                "Compression",
                (
                    f"{full_tokens / artifact.tokens:.2f}x "
                    f"({100 * (1 - artifact.tokens / full_tokens):.1f}% saved)"
                ),
            )
        )
    metrics.extend(
        [
            (
                "Selected tiers",
                " | ".join(
                    f"{level.as_str()}: {counts[level]}" for level in reversed(_LEVELS)
                ),
            ),
            ("Execution time", f"{elapsed_ms:.1f} ms"),
        ]
    )
    if output is not None:
        metrics.append(("Saved output", str(output)))

    summary = Table(
        title="ContextCraft compilation summary",
        box=box.SQUARE,
        header_style="bold cyan",
    )
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    for label, value in metrics:
        summary.add_row(label, value)
    stderr.print()
    stderr.print(summary)
    if not files:
        return

    ranked = Table(
        title="Top five files by personalized PageRank",
        caption="Source tokens only. Artifact tokens also include framing and path listings.",
        box=box.SQUARE,
        header_style="bold cyan",
    )
    ranked.add_column("File")
    ranked.add_column("Tier", justify="center")
    ranked.add_column("PageRank", justify="right")
    ranked.add_column("Tokens (selected / full)", justify="right")
    for file_id in sorted(
        files, key=lambda file_id: (-scores[file_id], files[file_id].path.as_posix())
    )[:5]:
        level = selected[file_id]
        selected_tokens = (
            0
            if level == FidelityLevel.TREE
            else full_counts[file_id]
            if level == FidelityLevel.FULL
            else counter.count(tiers[file_id][level].content)
        )
        ranked.add_row(
            files[file_id].path.as_posix(),
            level.as_str(),
            f"{100 * scores[file_id]:.1f}%",
            f"{selected_tokens:,} / {full_counts.get(file_id, 0):,}",
        )
    stderr.print()
    stderr.print(ranked)


def _render_debug(analysis: RepositoryAnalysis, config: Config) -> None:
    files = analysis.index.files
    tiers = {
        file_id: file_tiers.levels
        for file_id, file_tiers in analysis.tiers.files.items()
    }
    stderr.print(
        Pretty(
            {
                "repository": analysis.index.root,
                "files": {
                    file_id: file.path.as_posix() for file_id, file in files.items()
                },
                "scores": analysis.scores,
                "selection": {
                    file_id: level.as_str()
                    for file_id, level in analysis.artifact.selected_tiers.items()
                },
                "artifact": {
                    "tokens": analysis.artifact.tokens,
                    "estimated": analysis.artifact.token_counts_estimated,
                },
            }
        )
    )
    stderr.print("\n=== GRAPH ===", style="bold")
    stderr.print(
        Pretty(
            {
                "nodes": {
                    file_id: file.path.as_posix() for file_id, file in files.items()
                },
                "edges": analysis.graph.dependencies,
            }
        )
    )
    stderr.print("\n=== TIERS ===", style="bold")
    stderr.print(
        Pretty(
            {
                "encoding": config.tokenizer_encoding.as_str(),
                "costs": "cached or estimated framed tokens, not final artifact counts",
                "indexed_files": len(files),
                "loaded_files": len(analysis.repository.sources),
                "totals": {
                    level.as_str(): {
                        "files": sum(level in levels for levels in tiers.values()),
                        "framed_tokens": sum(
                            levels[level].framed_tokens
                            for levels in tiers.values()
                            if level in levels
                        ),
                    }
                    for level in _LEVELS
                },
                "files": {
                    file_id: {
                        "path": files[file_id].path.as_posix(),
                        "framed_tokens": {
                            level.as_str(): tier.framed_tokens
                            for level, tier in levels.items()
                        },
                    }
                    for file_id, levels in tiers.items()
                },
            }
        )
    )


@app.default
def compile_repository(
    path: Annotated[
        Path, Parameter(group=INPUT_GROUP, help="Repository directory")
    ] = Path("."),
    *,
    budget: Annotated[
        int,
        Parameter(
            group=OUTPUT_GROUP,
            alias="-b",
            converter=_parse_budget,
            help="Positive token budget, optionally suffixed with k or m",
        ),
    ] = _DEFAULTS.budget_tokens,
    output_format: Annotated[
        str,
        Parameter(
            group=OUTPUT_GROUP,
            name="--format",
            alias="-m",
            choices=tuple(_FORMATS),
            help="Output format",
        ),
    ] = "markdown",
    output: Annotated[
        Path | None,
        Parameter(
            group=OUTPUT_GROUP,
            alias="-o",
            allow_leading_hyphen=True,
            help="Output file, or - for stdout",
        ),
    ] = None,
    focus: Annotated[
        str | None,
        Parameter(
            group=FOCUS_GROUP, alias="-f", help="Query used to rank relevant files"
        ),
    ] = None,
    focus_file: Annotated[
        list[str] | None,
        Parameter(
            group=FOCUS_GROUP,
            consume_multiple=False,
            help="Path, filename, directory, or glob to favor. Repeatable",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        Parameter(
            group=INPUT_GROUP,
            alias="-e",
            consume_multiple=False,
            help="Additional repository-relative exclusion glob. Repeatable",
        ),
    ] = None,
    encoding: Annotated[
        str,
        Parameter(
            group=TOKEN_GROUP,
            alias=("-enc", "--tokenizer-encoding"),
            choices=tuple(_ENCODINGS),
            help="Tokenizer vocabulary for token accounting",
        ),
    ] = "cl100k_base",
    enable_parallel: Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--parallel",
            negative="--no-parallel",
            help="Analyze sources and render tiers in parallel",
        ),
    ] = _DEFAULTS.enable_parallel,
    allow_token_estimates: Annotated[
        bool,
        Parameter(
            group=TOKEN_GROUP,
            name="--token-estimates",
            negative="--no-token-estimates",
            help="Permit estimated token counts in the pipeline",
        ),
    ] = _DEFAULTS.allow_token_estimates,
    respect_gitignore: Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--gitignore",
            alias="--respect-gitignore",
            negative=("--no-gitignore", "--no-respect-gitignore"),
            help="Respect Git exclusion rules",
        ),
    ] = _DEFAULTS.respect_gitignore,
    redact_secrets: Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--redact",
            alias="--redact-secrets",
            negative=("--no-redact", "--no-redact-secrets"),
            help="Redact recognized secrets before analysis",
        ),
    ] = _DEFAULTS.redact_secrets,
    max_file_size_bytes: Annotated[
        int,
        Parameter(
            group=INPUT_GROUP,
            validator=Number(gt=0),
            help="Maximum source and manifest size in bytes",
        ),
    ] = _DEFAULTS.max_file_size_bytes,
    quiet: Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            alias="-q",
            help="Suppress the summary and ranked files",
        ),
    ] = False,
    debug: Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            help="Print ranking, graph, and tier diagnostics to stderr",
        ),
    ] = False,
) -> None:
    """Compress a local repository with the Rust-backed Python API.

    Write context to stdout or an output file, and diagnostics to stderr.
    Markdown is rendered when stdout is a terminal. Piped and saved artifacts
    retain their original content. Existing output files may be overwritten.
    """
    start = perf_counter()
    path = path.expanduser()
    output = output.expanduser() if output is not None and output != Path("-") else None
    exclusions = list(exclude or ())
    if output is not None:
        target = output.resolve()
        if target.is_dir():
            raise IsADirectoryError(f"output path is a directory: {output}")
        target.parent.resolve(strict=True)
        try:
            relative = target.relative_to(path.resolve(strict=True)).as_posix()
        except ValueError:
            pass
        else:
            # Match the exact output path, including any glob metacharacters.
            escaped = "".join(
                f"[{char}]" if char in "?*[]{}" else char for char in relative
            )
            exclusions.append("/" + escaped)

    config = Config(
        budget_tokens=budget,
        output_format=_FORMATS[output_format],
        focus_query=focus,
        focus_files=focus_file,
        exclude_patterns=exclusions,
        tokenizer_encoding=_ENCODINGS[encoding],
        enable_parallel=enable_parallel,
        allow_token_estimates=allow_token_estimates,
        redact_secrets=redact_secrets,
        respect_gitignore=respect_gitignore,
        max_file_size_bytes=max_file_size_bytes,
    )
    analysis = ContextCraft(config).run(path)
    elapsed_ms = (perf_counter() - start) * 1000
    if debug:
        _render_debug(analysis, config)
    _write_output(
        analysis.artifact.content,
        output,
        render_markdown=config.output_format == OutputFormat.MARKDOWN,
    )
    if not quiet:
        _render_summary(analysis, config, elapsed_ms, output)
    if analysis.artifact.token_counts_estimated:
        stderr.print(
            "warning: token counts are estimated. A strict budget fit is not guaranteed",
            style="yellow",
        )
