---
title: "contextcraft.cli"
description: "Load the optional Cyclopts and Rich command-line interface."
editUrl: false
sidebar:
  order: 4
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-blue-low); color: var(--sl-color-blue-high);">Python</span>

Load the optional Cyclopts and Rich command-line interface.

## Functions

### <span id="fn.main"></span><code style="font-size: 0.85em">main</code>

```python
def main(argv: Sequence[str] | None = None) -> int
```

Run the CLI, returning 0 on success, 1 on failure, or 2 for invalid arguments.

Requires Python 3.10 or newer and the ``contextcraft-ai[cli]`` extra.
Importing the SDK does not load these optional dependencies.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `argv` | `Sequence[str] | None` |  |

<details>
<summary>Source</summary>

```python
def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning 0 on success, 1 on failure, or 2 for invalid arguments.

    Requires Python 3.10 or newer and the ``contextcraft-ai[cli]`` extra.
    Importing the SDK does not load these optional dependencies.
    """
    try:
        from cyclopts import CycloptsError

        from ._cli import app, stderr
    except ModuleNotFoundError as error:
        if error.name is None or error.name.split(".")[0] not in {"cyclopts", "rich"}:
            raise
        print(
            'error: install CLI dependencies with pip install "contextcraft-ai[cli]"\n'
            "From this workspace, use uv run --package contextcraft-ai --extra cli contextcraft",
            file=sys.stderr,
        )
        return 1

    try:
        result = app(
            argv, exit_on_error=False, print_error=True, result_action="return_value"
        )
    except CycloptsError:
        return 2
    except BrokenPipeError:
        return 1
    except (OSError, ValueError, OverflowError, RuntimeError) as error:
        stderr.print(f"error: {error}", style="red", soft_wrap=True)
        return 1

    return result if isinstance(result, int) else 0
```

</details>
