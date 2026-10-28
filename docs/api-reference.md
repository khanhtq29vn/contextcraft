# API Reference

Use `contextcraft.ContextCraft` to compile a repository. Import configuration
from `contextcraft.config` and pipeline records from `contextcraft.models`.
The pages below describe the SDK, its data models, and the language interface.
Signatures are generated from the installed package.

```{toctree}
:maxdepth: 2

api/sdk
api/models
api/languages
```

## Command-line interface

Both `contextcraft` and `contextcraft-ai` expose the same command:

```bash
contextcraft [OPTIONS] [PATH]
contextcraft --help
```

`PATH` defaults to the current directory. For a directory, the command emits a
budgeted artifact to stdout or `--output`. The compilation summary and ranked
files go to stderr unless `--quiet` is set. `--debug` prints additional pipeline
diagnostics to stderr, even with `--quiet`.

For a single Python file, the command prints its skeleton and signatures instead
of compiling a repository. This mode does not apply the token budget or redact
secrets.

| Option                                       | Description                                                                  | Default       |
| :------------------------------------------- | :--------------------------------------------------------------------------- | :------------ |
| `--budget`, `-b`                             | Positive integer token budget; shorthand such as `16k` is not accepted       | `16000`       |
| `--encoding`, `-enc`, `--tokenizer-encoding` | Tiktoken encoding for token accounting                                       | `cl100k_base` |
| `--focus`, `-f`                              | Query used to prefer relevant files                                          | None          |
| `--focus-file`                               | Repository-relative path, filename, directory, or glob to prefer; repeatable | None          |
| `--format`, `-m`                             | `markdown`, `xml`, or `json`                                                 | `markdown`    |
| `--output`, `-o`                             | Write output to a file, creating parent directories if needed                | None          |
| `--exclude`, `-e`                            | Additional ignore glob; repeatable                                           | None          |
| `--no-redact`, `--no-redact-secrets`         | Disable recognized-secret redaction                                          | Off           |
| `--no-gitignore`, `--no-respect-gitignore`   | Disable Git ignore rules; language and explicit exclusions still apply       | Off           |
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

An existing output file is overwritten. For directory compilation, an output
path inside the repository is excluded from indexing.
