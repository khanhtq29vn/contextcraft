---
title: CLI options
description: Look up input, focus, output, token accounting, and diagnostic options.
---

```sh
contextcraft [DIRECTORY] [OPTIONS]
```

The directory defaults to the current working directory. Run `contextcraft --help` to see the options available in your installed version.

## Input and scanning

| Option                           | Default   | Purpose                                                                |
| -------------------------------- | --------- | ---------------------------------------------------------------------- |
| `--exclude PATTERN`              | None      | Exclude a repository-relative glob. Repeat for multiple patterns.      |
| `--gitignore` / `--no-gitignore` | Enabled   | Respect Git exclusion rules. Language-specific exclusions still apply. |
| `--redact` / `--no-redact`       | Enabled   | Redact recognized secrets before parsing.                              |
| `--max-file-size-bytes INTEGER`  | `1048576` | Positive source and manifest read limit, in bytes.                     |
| `--parallel` / `--no-parallel`   | Enabled   | Enable parallel source analysis and tier rendering.                    |

## Focus

| Option               | Purpose                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| `--focus TEXT`, `-f` | Task query used for relevance ranking.                                  |
| `--focus-file PATH`  | Favor a path, filename, directory, or glob. Repeat for multiple values. |

Focus is a hint rather than an inclusion guarantee. See [focus on a task](../../guides/focus/).

## Output and tokens

| Option                                       | Default       | Purpose                                                                                    |
| -------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------ |
| `--budget TOKENS`                            | `16k`         | Positive maximum for the complete artifact. Accepts `k` and `m` suffixes.                  |
| `--format FORMAT`                            | `markdown`    | `markdown`, `xml`, or `json`.                                                              |
| `--output PATH`, `-o`                        | stdout        | Write the artifact to a UTF-8 file. `-` also means stdout.                                 |
| `--encoding NAME`                            | `cl100k_base` | Tokenizer vocabulary used for accounting.                                                  |
| `--token-estimates` / `--no-token-estimates` | Enabled       | Permit estimated pipeline counts. The current tokenizer counts exactly without a fallback. |

See [token budgets](../../guides/token-budgets/) for encoding labels. Create the parent output directory before writing a file. Existing output files can be overwritten.

## Diagnostics

| Option      | Purpose                                             |
| ----------- | --------------------------------------------------- |
| `--quiet`   | Suppress the compilation summary, but not warnings. |
| `--debug`   | Include ranking, graph, and tier diagnostics.       |
| `--help`    | Show command help.                                  |
| `--version` | Show the installed version.                         |

The artifact goes to stdout or the output file. Summaries and diagnostics go to stderr. Exit status is `0` for success, `1` for operational failure, and `2` for invalid arguments.
