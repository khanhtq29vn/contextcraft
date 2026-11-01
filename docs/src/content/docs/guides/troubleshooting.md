---
title: Troubleshooting
description: Recover from installation, input, budget, and output errors.
---

## The command is not found

Use the Python environment where the package was installed:

```sh
python -m contextcraft --help
```

If necessary, reinstall with `python -m pip install "contextcraft-ai[cli]"` in that environment. See [installation](../../getting-started/installation/).

## CLI dependencies are missing

The SDK-only installation does not include Cyclopts or Rich. Install the extra:

```sh
pip install "contextcraft-ai[cli]"
```

## The repository path is invalid

Pass an existing local directory that you can read. The CLI does not accept a single file or a remote repository URL. Clone remote repositories locally before running ContextCraft.

## The budget cannot fit the output

Increase `--budget`. Even a minimal artifact needs framing and paths. You can also narrow the scan with [exclusions](../files/).

## Expected code is absent

Check Git ignore rules, exclusions, file-size limits, and source encoding. A file may be represented only by its path or signatures. [Focus paths](../focus/) can improve a file’s ranking, while a larger budget can allow more detail. Neither guarantees inclusion.

## The output cannot be written

Create the parent output directory first and check write permissions. Existing files can be overwritten. Use `--output -` to write the artifact to stdout instead.

## Inspect diagnostics

```sh
contextcraft . --budget 8k --debug -o context.md
```

Debug output includes graph, ranking, and tier diagnostics. Some unselected tier costs may be estimates and are labeled accordingly. Exit status `0` means success, `1` means an operational failure, and `2` means invalid arguments.
