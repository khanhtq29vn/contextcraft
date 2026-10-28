# Compiler

```{eval-rst}
.. autoclass:: contextcraft.ContextCraft

.. py:method:: contextcraft.ContextCraft.compile(path: str | pathlib.Path) -> contextcraft.models.Artifact

   Compile a repository and return a budgeted artifact.
```

Create a compiler with `ContextCraft(config=None, *,
languages=BUILTIN_LANGUAGES)`, either omitting `config` for a new default
configuration or supplying an instance to share with the compiler. Changes to
a shared config affect subsequent compilations, and a supplied `languages`
tuple replaces rather than extends the built-in set.

`compile(path)` accepts a string or `pathlib.Path`, scanning either the
directory itself or the parent of a supplied file. Every call reads and
analyzes the repository again, whether or not it is a Git checkout, without a
snapshot or separate `analyze()` API.

The returned [Artifact](models.md) contains the output text, token count,
estimate status, and final tier for every indexed file. To retain the index or
scores as well, use the [pipeline stages](stages.md) directly rather than
relying on the artifact to hold intermediate results.

See [Use the Python SDK](../../guides/python-sdk.md) for examples and
[Configuration](../configuration.md) for field defaults and validation.

## Errors

The SDK propagates pipeline and dependency exceptions without wrapping them
in a package-specific exception hierarchy.

- `OSError`, including `FileNotFoundError` and `NotADirectoryError`, reports
  unreadable paths or sources.
- `ValueError` reports an invalid allocation budget, framing that cannot fit,
  or an invalid tokenizer encoding. Lower-level stages also validate file
  coverage and score values.
- `KeyError` reports missing referenced records or detected language implementations.
- `msgspec.ValidationError` reports invalid input during typed decoding or conversion.

Other dependency errors, including walker, parser, and tokenizer failures,
propagate unless the relevant stage explicitly handles them. Enabling secret
redaction does not guarantee that every secret is detected.
