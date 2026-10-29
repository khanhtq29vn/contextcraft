# Configuration

```{eval-rst}
.. autoclass:: contextcraft.config.Config
```

`Config` is a mutable, keyword-only `msgspec.Struct`. Use enum members for
`output_format` and `tokenizer_encoding` when constructing it directly.

| Field                   | Default                         | Meaning                                                               |
| :---------------------- | :------------------------------ | :-------------------------------------------------------------------- |
| `workers`               | `1`                             | Positive worker count for file loading and tier rendering             |
| `budget_tokens`         | `16000`                         | Positive integer output token budget                                  |
| `focus_query`           | `None`                          | Query used to prefer relevant files                                   |
| `focus_files`           | `[]`                            | Repository-relative paths, filenames, directories, or globs to prefer |
| `output_format`         | `OutputFormat.MARKDOWN`         | Artifact format                                                       |
| `exclude_patterns`      | `[]`                            | Additional ignore globs                                               |
| `respect_gitignore`     | `True`                          | Respect Git ignore rules during indexing                              |
| `redact_secrets`        | `True`                          | Redact recognized secrets before source analysis                      |
| `max_file_size_bytes`   | `1048576`                       | Positive maximum source size in bytes                                 |
| `tokenizer_encoding`    | `TokenizerEncoding.CL100K_BASE` | Tiktoken encoding for token accounting                                |
| `allow_token_estimates` | `True`                          | Allow approximate counts if tokenization fails                        |

Use `msgspec.convert()` or a typed msgspec decoder when you need field types
and constraints validated, because direct construction and assignment do not
perform those checks. Typed conversion and decoding also reject unknown
fields. Budgets must be integers rather than shorthand values such as `"16k"`.

```python
import msgspec

from contextcraft.config import Config

config = msgspec.convert(
    {"budget_tokens": 8000, "output_format": "json"},
    type=Config,
)
```

```{eval-rst}
.. autoclass:: contextcraft.config.OutputFormat
   :members:

.. autoclass:: contextcraft.config.TokenizerEncoding
   :members:
```
