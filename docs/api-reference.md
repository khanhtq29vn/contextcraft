# API Reference

The Python SDK entry point is `contextcraft.ContextCraft`. The pages below
cover compilation, result models, AST data, and language extension interfaces.
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

`PATH` defaults to the current directory. Artifacts go to stdout unless
`--output` is set; telemetry goes to stderr unless `--quiet` is set.

| Option               | Description                                                                         | Default       |
| :------------------- | :---------------------------------------------------------------------------------- | :------------ |
| `--budget`, `-b`     | Token budget, as an integer or shorthand such as `16k`                              | `32k`         |
| `--encoding`, `-enc` | Tiktoken encoding name used for token accounting (e.g. `cl100k_base`, `o200k_base`) | `cl100k_base` |
| `--focus`, `-f`      | Query or symbol keywords to bias ranking                                            | None          |
| `--focus-file`       | Relative file path or glob to boost (repeatable)                                    | None          |
| `--format`, `-m`     | `markdown`, `xml`, or `json` (case-insensitive)                                     | `markdown`    |
| `--output`, `-o`     | Write the artifact to a file                                                        | None          |
| `--include`, `-i`    | Include glob (repeatable)                                                           | None          |
| `--exclude`, `-e`    | Additional exclude glob (repeatable)                                                | None          |
| `--copy`, `-c`       | Copy the artifact to the clipboard                                                  | Off           |
| `--no-redact`        | Disable secret redaction                                                            | Off           |
| `--no-gitignore`     | Ignore neither `.gitignore` nor `.contextignore` rules                              | Off           |
| `--quiet`, `-q`      | Suppress telemetry                                                                  | Off           |
| `--version`, `-V`    | Show the version and exit                                                           |               |
| `--help`             | Show usage and exit                                                                 |               |

```bash
contextcraft . --budget 16k --focus-file 'src/**' --format xml -o context.xml
```
