"""Expose repository compilation and single-file Python outlines through the CLI."""

from __future__ import annotations

import sys
from collections import Counter
from glob import escape
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Annotated

import ignore
import tree_sitter as ts
from cyclopts import App, CycloptsError, Group, Parameter
from cyclopts.help import ColumnSpec, DefaultFormatter, PanelSpec, TableSpec
from cyclopts.help.specs import DescriptionRenderer, NameRenderer
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.pretty import Pretty
from rich.table import Table

from contextcraft.config import Config, OutputFormat, TokenizerEncoding
from contextcraft.formatter import ArtifactFormatter
from contextcraft.graph import GraphBuilder, GraphScorer
from contextcraft.imports import ImportResolver
from contextcraft.index import Indexer
from contextcraft.languages.python.language import PythonLanguage, get_py_grammar
from contextcraft.models import Artifact, FidelityLevel, Index, Source, Tiers
from contextcraft.optimizer import BudgetAllocator
from contextcraft.source import SourceLoader
from contextcraft.tiers import TierRenderer

DEFAULT_BUDGET_TOKENS = Config().budget_tokens
DEFAULT_MAX_FILE_SIZE_BYTES = Config().max_file_size_bytes

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
                renderer=NameRenderer(),
                header="Option",
                width=28,
                overflow="fold",
            ),
            ColumnSpec(
                renderer=DescriptionRenderer(),
                header="Description",
                overflow="fold",
            ),
        ),
    ),
    group_arguments=INPUT_GROUP,
    group_commands=GENERAL_GROUP,
    version=version("contextcraft-ai"),
    version_flags=("--version", "-V"),
)


def _write_output(
    content: str, output: Path | None, *, render_markdown: bool = False
) -> None:
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    elif render_markdown and sys.stdout.isatty():
        Console().print(Markdown(content))
    else:
        sys.stdout.write(content)
        sys.stdout.flush()


def _render_summary(
    *,
    index: Index,
    source: Source,
    tiers: Tiers,
    scores: dict[int, float],
    artifact: Artifact,
    config: Config,
    elapsed_ms: float,
    output: Path | None,
) -> None:
    full_tokens = sum(
        file_tiers[FidelityLevel.FULL].tokens
        for file_tiers in tiers.files.values()
        if FidelityLevel.FULL in file_tiers
    )
    counts = Counter(artifact.selected_tiers.values())
    metrics = [
        ("Repository", str(index.path)),
        ("Indexed / loaded files", f"{len(index.files)} / {len(source.content)}"),
        ("Skipped sources", str(len(index.files) - len(source.content))),
        ("Encoding", config.tokenizer_encoding.value),
        ("Full-source tokens", f"{full_tokens:,}"),
        (
            "Output tokens / budget",
            f"{artifact.tokens:,} / {config.budget_tokens:,} ({100 * artifact.tokens / config.budget_tokens:.1f}%)",
        ),
        (
            "Token counts",
            "Estimated (no exact budget guarantee)"
            if artifact.token_counts_estimated
            else "Exact",
        ),
    ]

    if full_tokens:
        metrics.append(
            (
                "Compression",
                f"{full_tokens / artifact.tokens:.2f}x ({100 * (1 - artifact.tokens / full_tokens):.1f}% saved)",
            )
        )

    metrics.extend(
        [
            (
                "Selected tiers",
                " | ".join(
                    f"{level.name}: {counts[level]}"
                    for level in reversed(FidelityLevel)
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

    if not index.files:
        return

    ranked = Table(
        title="Top five files by personalized PageRank",
        box=box.SQUARE,
        header_style="bold cyan",
    )
    ranked.add_column("File")
    ranked.add_column("Tier", justify="center")
    ranked.add_column("PageRank", justify="right")
    ranked.add_column("Tokens (selected / full)", justify="right")

    for file_id in sorted(
        index.files,
        key=lambda file_id: (-scores[file_id], index.files[file_id].path.as_posix()),
    )[:5]:
        level = artifact.selected_tiers[file_id]
        file_tiers = tiers.files[file_id]
        full = file_tiers.get(FidelityLevel.FULL)
        path = index.files[file_id].path.relative_to(index.path).as_posix()
        ranked.add_row(
            path,
            level.name,
            f"{100 * scores[file_id]:.1f}%",
            f"{file_tiers[level].tokens:,} / {full.tokens if full is not None else 0:,}",
        )

    stderr.print()
    stderr.print(ranked)


@app.default
def main(
    path: Annotated[
        Path, Parameter(group=INPUT_GROUP, help="Directory or Python source file")
    ] = Path("."),
    *,
    budget: Annotated[
        int,
        Parameter(group=OUTPUT_GROUP, alias="-b", help="Positive output token budget"),
    ] = DEFAULT_BUDGET_TOKENS,
    output_format: Annotated[
        OutputFormat,
        Parameter(
            group=OUTPUT_GROUP, name="--format", alias="-m", help="Output format"
        ),
    ] = OutputFormat.MARKDOWN,
    output: Annotated[
        Path | None,
        Parameter(
            group=OUTPUT_GROUP,
            alias="-o",
            help="Write output to this file instead of stdout",
        ),
    ] = None,
    debug: Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            help="Print pipeline results, graph, and tier diagnostics to stderr",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            alias="-q",
            help="Suppress the compilation summary and ranked files",
        ),
    ] = False,
    focus: Annotated[
        str | None,
        Parameter(
            group=FOCUS_GROUP,
            alias="-f",
            help="Query used to prefer relevant repository files",
        ),
    ] = None,
    focus_file: Annotated[
        list[str] | None,
        Parameter(
            group=FOCUS_GROUP,
            consume_multiple=False,
            help="Prefer a repository-relative path, filename, directory, or glob; repeatable",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        Parameter(
            group=INPUT_GROUP,
            alias="-e",
            consume_multiple=False,
            help="Additional ignore glob; repeatable",
        ),
    ] = None,
    encoding: Annotated[
        TokenizerEncoding,
        Parameter(
            group=TOKEN_GROUP,
            alias=("-enc", "--tokenizer-encoding"),
            name_transform=str.lower,
            help="Tiktoken encoding used for token accounting",
        ),
    ] = TokenizerEncoding.CL100K_BASE,
    respect_gitignore: Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--gitignore",
            alias="--respect-gitignore",
            negative=("--no-gitignore", "--no-respect-gitignore"),
            help="Respect .gitignore rules",
        ),
    ] = True,
    redact_secrets: Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--redact",
            alias="--redact-secrets",
            negative=("--no-redact", "--no-redact-secrets"),
            help="Redact recognized secrets before analysis",
        ),
    ] = True,
    max_file_size_bytes: Annotated[
        int, Parameter(group=INPUT_GROUP, help="Maximum source file size in bytes")
    ] = DEFAULT_MAX_FILE_SIZE_BYTES,
    allow_token_estimates: Annotated[
        bool,
        Parameter(
            group=TOKEN_GROUP,
            help="Allow approximate counts if tokenization fails; exact budgets are not guaranteed",
        ),
    ] = False,
) -> None:
    """Compile a directory or print a Python file's skeleton and signatures.

    CLI parameters describe filtering, ranking, token accounting, and output.
    Directory output is budgeted and redacted according to those options;
    single-file output is not budgeted or redacted. Write content to stdout
    or output, and diagnostics to stderr. An output file may be overwritten.

    Raises:
        SystemExit: With code 2 for invalid budgets, file-size limits, or
            handled file, encoding, configuration, and walker errors.
    """
    if budget <= 0:
        stderr.print("error: --budget must be positive", style="red")
        raise SystemExit(2)

    if max_file_size_bytes <= 0:
        stderr.print("error: --max-file-size-bytes must be positive", style="red")
        raise SystemExit(2)

    start = perf_counter()

    try:
        path = path.expanduser()
        output = output.expanduser() if output is not None else None

        if output is not None and path.is_file() and output.resolve() == path.resolve():
            raise ValueError("Output must not overwrite the input source file")

        if path.is_dir():
            exclusions = list(exclude or ())

            if output is not None:
                root = path.resolve()

                for candidate in {output.absolute(), output.resolve()}:
                    if candidate.is_relative_to(root):
                        exclusions.append(
                            "/" + escape(candidate.relative_to(root).as_posix())
                        )

            config = Config(
                budget_tokens=budget,
                output_format=output_format,
                focus_query=focus,
                focus_files=focus_file or [],
                exclude_patterns=exclusions,
                tokenizer_encoding=encoding,
                respect_gitignore=respect_gitignore,
                redact_secrets=redact_secrets,
                max_file_size_bytes=max_file_size_bytes,
                allow_token_estimates=allow_token_estimates,
            )

            index = Indexer().index(path, config)
            source = SourceLoader().load(index, config)
            resolutions = ImportResolver().resolve(index, source)
            graph = GraphBuilder().build(index, source, resolutions)
            scores = GraphScorer().score(index, source, graph, config)
            tiers = TierRenderer().render(index, source, config)
            selection = BudgetAllocator().allocate(index, tiers, scores, config)
            artifact = ArtifactFormatter().format(
                index, tiers, scores, selection, config
            )

            elapsed_ms = (perf_counter() - start) * 1000

            if debug:
                stderr.print(
                    Pretty(
                        {
                            "index": index,
                            "source": source,
                            "resolutions": resolutions,
                            "scores": scores,
                            "selection": selection,
                            "artifact": artifact,
                        }
                    )
                )
                stderr.print("\n=== GRAPH ===", style="bold")
                stderr.print(
                    Pretty(
                        {
                            "nodes": {
                                file_id: file.path.relative_to(index.path).as_posix()
                                for file_id, file in index.files.items()
                            },
                            "edges": [
                                (graph[source], graph[target], weight)
                                for source, target, weight in graph.weighted_edge_list()
                            ],
                        },
                    )
                )
                stderr.print("\n=== TIERS ===", style="bold")
                stderr.print(
                    Pretty(
                        {
                            "encoding": config.tokenizer_encoding.value,
                            "token_counts_estimated": artifact.token_counts_estimated,
                            "indexed_files": len(index.files),
                            "loaded_files": len(source.content),
                            "tree_only_files": len(index.files) - len(source.content),
                            "totals": {
                                level.name: {
                                    "files": sum(
                                        level in file_tiers
                                        for file_tiers in tiers.files.values()
                                    ),
                                    "tokens": sum(
                                        file_tiers[level].tokens
                                        for file_tiers in tiers.files.values()
                                        if level in file_tiers
                                    ),
                                }
                                for level in FidelityLevel
                            },
                            "files": {
                                file_id: {
                                    "path": index.files[file_id]
                                    .path.relative_to(index.path)
                                    .as_posix(),
                                    "tokens": {
                                        level.name: tier.tokens
                                        for level, tier in file_tiers.items()
                                    },
                                }
                                for file_id, file_tiers in tiers.files.items()
                            },
                        },
                    )
                )

            _write_output(
                artifact.content,
                output,
                render_markdown=config.output_format == OutputFormat.MARKDOWN,
            )

            if not quiet:
                _render_summary(
                    index=index,
                    source=source,
                    tiers=tiers,
                    scores=scores,
                    artifact=artifact,
                    config=config,
                    elapsed_ms=elapsed_ms,
                    output=output,
                )

            return

        source = path.read_bytes()
        parser = ts.Parser(get_py_grammar())
        skel = PythonLanguage.render_skel(source, parser)
        sigs = PythonLanguage.render_sigs(source, parser)
        content = (
            "=== SKEL ===\n"
            + skel
            + ("" if skel.endswith("\n") else "\n")
            + "\n=== SIGS ===\n"
            + sigs
            + ("" if sigs.endswith("\n") else "\n")
        )
        _write_output(content, output)

        if output is not None and not quiet:
            stderr.print(f"Saved output: {output}", soft_wrap=True)

    except (OSError, UnicodeError, ValueError, ignore.Error, ignore.IOError) as exc:
        stderr.print(f"error: {exc}", style="red", soft_wrap=True)
        raise SystemExit(2) from None


def run_cli() -> None:
    """Run the CLI and report argument errors with exit code 2.

    Arguments are read from sys.argv. Results go to stdout or the requested
    output file; argument errors and compilation diagnostics go to stderr.
    """
    try:
        app(exit_on_error=False, print_error=True, result_action="return_value")
    except CycloptsError:
        raise SystemExit(2) from None
