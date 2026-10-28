# Getting started

Use ContextCraft on a local repository with `uvx` or an installed CLI,
without setting up a separate development environment.

## Run without a permanent installation

Install [uv](https://docs.astral.sh/uv/), then use `uvx` to run the published CLI
in an isolated environment:

```bash
uvx --from 'contextcraft-ai[cli]' contextcraft . --budget 8000 -o context.md
```

`uvx` downloads and caches an isolated environment with the command-line
dependencies supplied by `[cli]`, without adding ContextCraft to your project
or installing it globally.

## Install a reusable command

If you use the CLI regularly, install it as a tool:

```bash
uv tool install 'contextcraft-ai[cli]'
contextcraft . --budget 8000 -o context.md
```

## Read the result

The command writes a Markdown artifact to `context.md`, excluding that path
from the scan if it falls inside the repository. Any existing file at that
path is overwritten.

The terminal summary reports the number of indexed and loaded files, the
output token count, and the fidelity levels chosen for the artifact. Depending
on the available budget, a file may appear as full source, a declaration
outline, or only a path, and the path listing itself may be shortened to leave
room for code.

Specify the budget as an integer, such as `8000`, rather than `8k`. Token
counting tries tiktoken first, falling back to estimates if loading or
encoding fails. When the summary reports estimated counts, the output is no
longer guaranteed to fit the exact token budget.

Review the artifact before sharing it, even with the default redaction
enabled, because secret detection cannot catch every credential.

Continue with [Use the CLI](guides/cli.md) for task-focused examples or [Use
the Python SDK](guides/python-sdk.md) to call ContextCraft from your
application. If you are working on ContextCraft itself, the [contribution
guide](https://github.com/khanhtq29vn/contextcraft/blob/main/CONTRIBUTING.md)
covers development setup.
