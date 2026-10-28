# Use the CLI

The examples below use an installed `contextcraft` command and assume you are
in the repository you want to compile. To work from another directory, replace
`.` with the repository path. You can also run without a permanent
installation by replacing the command with `uvx --from 'contextcraft-ai[cli]'
contextcraft`.

See [Getting started](../getting-started.md) for installation and `uvx` usage.

## Focus on a task

Use a short query that names the behavior you are working on:

```bash
contextcraft . --budget 8000 --focus "authentication token refresh" -o context.md
```

The query changes file rankings without limiting which files are scanned.
Prefer specific files or directories with repeatable `--focus-file` options:

```bash
contextcraft . --budget 8000 \
  --focus-file 'src/auth/**' \
  --focus-file 'session.py' \
  -o context.md
```

Focus makes a file more likely to receive a richer tier, but does not
guarantee full fidelity, since allocation still weighs its score against its
token cost and the available budget.

## Exclude files

Use repeatable ignore globs to leave files out of indexing:

```bash
contextcraft . --budget 8000 \
  --exclude 'generated/**' \
  --exclude 'fixtures/**' \
  -o context.md
```

By default, the scanner applies Git ignore rules alongside language-specific
exclusions and your `--exclude` patterns. Passing `--no-gitignore` disables
only the Git rules, and `.contextignore` is not read as a custom ignore file.

## Choose a format and tokenizer

```bash
contextcraft . --budget 16000 --format xml --encoding o200k_base -o context.xml
contextcraft . --budget 8000 --format json -o context.json
```

Choose the encoding that matches your downstream model when possible, keeping
in mind that the budget covers the complete artifact, including formatting and
the path listing, rather than source text alone.

When stdout is an interactive terminal, Markdown is rendered for display.
Redirect stdout or use `--output` to obtain the raw artifact, and add
`--quiet` if you also want to hide the summary normally written to stderr.

## Inspect the pipeline

```bash
contextcraft . --budget 8000 --debug -o context.md
```

Debug output includes the index, loaded source, import resolutions, scores,
graph edges, and tier diagnostics, so it can be much larger than the artifact
itself. Review it before sharing, especially with `--no-redact`, which can
expose recognized secrets in plain text. Debug output remains enabled even
when `--quiet` suppresses the summary.

## Inspect a Python file

```bash
contextcraft src/example.py
```

Passing a file path prints its Python `SKEL` and `SIGS` outlines instead of
compiling a repository artifact, and neither the output budget nor secret
redaction applies in this mode. Pass the containing directory when you want
budgeted repository context instead.

See the [CLI reference](../reference/cli.md) for all flags and defaults.
