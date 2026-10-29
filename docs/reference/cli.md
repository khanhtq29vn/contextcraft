# CLI reference

Both `contextcraft` and `contextcraft-ai` expose the same command:

```bash
contextcraft [OPTIONS] [PATH]
contextcraft --help
```

`PATH` defaults to the current directory, producing a budgeted artifact on
stdout or at the path supplied through `--output`. The compilation summary and
ranked files go to stderr unless `--quiet` suppresses them, while `--debug`
adds pipeline diagnostics that remain visible even in quiet mode.

When `PATH` names a single Python file, the command prints its skeleton and
signatures instead of compiling a repository, without applying the token
budget or redacting secrets.

| Option                                       | Description                                                                  | Default       |
| :------------------------------------------- | :--------------------------------------------------------------------------- | :------------ |
| `--workers`, `-j`                            | Positive worker count for parallel file loading and tier rendering           | `1`           |
| `--budget`, `-b`                             | Positive integer token budget, without shorthand such as `16k`               | `16000`       |
| `--encoding`, `-enc`, `--tokenizer-encoding` | Tiktoken encoding for token accounting                                       | `cl100k_base` |
| `--focus`, `-f`                              | Query used to prefer relevant files                                          | None          |
| `--focus-file`                               | Prefer a repository-relative path, filename, directory, or glob (repeatable) | None          |
| `--format`, `-m`                             | `markdown`, `xml`, or `json`                                                 | `markdown`    |
| `--output`, `-o`                             | Write output to a file, creating parent directories if needed                | None          |
| `--exclude`, `-e`                            | Additional ignore glob (repeatable)                                          | None          |
| `--no-redact`, `--no-redact-secrets`         | Disable recognized-secret redaction                                          | Off           |
| `--no-gitignore`, `--no-respect-gitignore`   | Disable Git ignore rules while keeping language and explicit exclusions      | Off           |
| `--max-file-size-bytes`                      | Maximum source file size in bytes                                            | `1048576`     |
| `--debug`                                    | Print pipeline records, graph edges, and tier diagnostics                    | Off           |
| `--quiet`, `-q`                              | Suppress the compilation summary and ranked-file table                       | Off           |
| `--version`, `-V`                            | Show the version and exit                                                    |               |
| `--help`                                     | Show usage and exit                                                          |               |

Redaction and Git ignore rules are enabled by default. Their positive flags are
`--redact` / `--redact-secrets` and `--gitignore` / `--respect-gitignore`.

Token counting falls back to estimates if tokenization fails. The compilation
summary reports estimated counts, which do not guarantee an exact token budget.

```bash
contextcraft . --budget 16000 --focus-file 'src/**' --format xml -o context.xml
```

The command overwrites an existing output file and, during directory
compilation, excludes that path from indexing if it falls inside the
repository.
