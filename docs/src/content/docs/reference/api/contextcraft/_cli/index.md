---
title: "contextcraft._cli"
description: "Cyclopts commands and Rich output for the optional CLI extra."
editUrl: false
sidebar:
  order: 3
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-blue-low); color: var(--sl-color-blue-high);">Python</span>

Cyclopts commands and Rich output for the optional CLI extra.

## Variables

| Name | Type | Description |
|------|------|-------------|
| `INPUT_GROUP` |  |  |
| `OUTPUT_GROUP` |  |  |
| `FOCUS_GROUP` |  |  |
| `TOKEN_GROUP` |  |  |
| `DIAGNOSTICS_GROUP` |  |  |
| `GENERAL_GROUP` |  |  |
| `stderr` |  |  |
| `app` |  |  |

## Functions

### <span id="fn.compile_repository"></span><code style="font-size: 0.85em">compile_​repository</code>

```python
def compile_repository(
    path: Annotated[
        Path, Parameter(group=INPUT_GROUP, help="Repository directory")
    ] = Path("."),
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
) -> None
```

Compress a local repository with the Rust-backed Python API.

Write context to stdout or an output file, and diagnostics to stderr.
Markdown is rendered when stdout is a terminal. Piped and saved artifacts
retain their original content. Existing output files may be overwritten.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `path` | `Annotated[
        Path, Parameter(group=INPUT_GROUP, help="Repository directory")
    ]` |  |
| `budget` | `Annotated[
        int,
        Parameter(
            group=OUTPUT_GROUP,
            alias="-b",
            converter=_parse_budget,
            help="Positive token budget, optionally suffixed with k or m",
        ),
    ]` |  |
| `output_format` | `Annotated[
        str,
        Parameter(
            group=OUTPUT_GROUP,
            name="--format",
            alias="-m",
            choices=tuple(_FORMATS),
            help="Output format",
        ),
    ]` |  |
| `output` | `Annotated[
        Path | None,
        Parameter(
            group=OUTPUT_GROUP,
            alias="-o",
            allow_leading_hyphen=True,
            help="Output file, or - for stdout",
        ),
    ]` |  |
| `focus` | `Annotated[
        str | None,
        Parameter(
            group=FOCUS_GROUP, alias="-f", help="Query used to rank relevant files"
        ),
    ]` |  |
| `focus_file` | `Annotated[
        list[str] | None,
        Parameter(
            group=FOCUS_GROUP,
            consume_multiple=False,
            help="Path, filename, directory, or glob to favor. Repeatable",
        ),
    ]` |  |
| `exclude` | `Annotated[
        list[str] | None,
        Parameter(
            group=INPUT_GROUP,
            alias="-e",
            consume_multiple=False,
            help="Additional repository-relative exclusion glob. Repeatable",
        ),
    ]` |  |
| `encoding` | `Annotated[
        str,
        Parameter(
            group=TOKEN_GROUP,
            alias=("-enc", "--tokenizer-encoding"),
            choices=tuple(_ENCODINGS),
            help="Tokenizer vocabulary for token accounting",
        ),
    ]` |  |
| `enable_parallel` | `Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--parallel",
            negative="--no-parallel",
            help="Analyze sources and render tiers in parallel",
        ),
    ]` |  |
| `allow_token_estimates` | `Annotated[
        bool,
        Parameter(
            group=TOKEN_GROUP,
            name="--token-estimates",
            negative="--no-token-estimates",
            help="Permit estimated token counts in the pipeline",
        ),
    ]` |  |
| `respect_gitignore` | `Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--gitignore",
            alias="--respect-gitignore",
            negative=("--no-gitignore", "--no-respect-gitignore"),
            help="Respect Git exclusion rules",
        ),
    ]` |  |
| `redact_secrets` | `Annotated[
        bool,
        Parameter(
            group=INPUT_GROUP,
            name="--redact",
            alias="--redact-secrets",
            negative=("--no-redact", "--no-redact-secrets"),
            help="Redact recognized secrets before analysis",
        ),
    ]` |  |
| `max_file_size_bytes` | `Annotated[
        int,
        Parameter(
            group=INPUT_GROUP,
            validator=Number(gt=0),
            help="Maximum source and manifest size in bytes",
        ),
    ]` |  |
| `quiet` | `Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            alias="-q",
            help="Suppress the summary and ranked files",
        ),
    ]` |  |
| `debug` | `Annotated[
        bool,
        Parameter(
            group=DIAGNOSTICS_GROUP,
            help="Print ranking, graph, and tier diagnostics to stderr",
        ),
    ]` |  |

<details>
<summary>Source</summary>

```python
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
```

</details>
