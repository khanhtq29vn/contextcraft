# Language interface

## Selecting languages

`contextcraft.languages.BUILTIN_LANGUAGES` supplies the default tuple of
language classes, currently containing `PythonLanguage` with no registered
Rust implementation.

Select implementations by passing a replacement tuple to `ContextCraft` or
`Indexer`, including `BUILTIN_LANGUAGES` in that tuple when you want to retain
built-in support.

```python
from contextcraft import ContextCraft
from contextcraft.config import Config
from contextcraft.languages.python.language import PythonLanguage

compiler = ContextCraft(Config(budget_tokens=8000), languages=(PythonLanguage,))
artifact = compiler.compile(".")
```

There is no separate registry or alias API, so implementations should use
distinct language IDs. Detection checks suffixes and exact filenames
case-sensitively in tuple order, accepting the first match even when a later
implementation matches the exact filename rather than the suffix.

Indexing records each file's language in `File.language_id` and stores the
detected implementations in `Index.languages` for later stages to reuse. Every
non-null ID must have an entry in that mapping or its use raises `KeyError`,
whereas an unrecognized file has `language_id=None` and retains full source
without language-specific analysis.

## Language contract

Subclass `contextcraft.languages.base.Language` and implement its static methods.
Methods that analyze or render source receive UTF-8 bytes, after redaction when
that option is enabled. Rendering methods return text outlines, which need not
be executable source.

```{eval-rst}
.. autoclass:: contextcraft.languages.base.Language
   :members: get_language_id, get_file_extensions, get_filenames, get_root_files, get_package_files, get_ignore_patterns, extract_docstrings, extract_imports, resolve_imports, render_sigs, render_skel
```

### File and project metadata

| Method                  | Required result                                                  |
| :---------------------- | :--------------------------------------------------------------- |
| `get_language_id()`     | Stable language ID stored on files and used in `Index.languages` |
| `get_file_extensions()` | Recognized suffixes with leading dots, such as `.py`             |
| `get_filenames()`       | Recognized exact filenames, including extensionless scripts      |
| `get_root_files()`      | Filenames whose parent directories mark project roots            |
| `get_package_files()`   | Filenames associated with package metadata and dependencies      |
| `get_ignore_patterns()` | Default exclusion globs applied during indexing                  |

`Indexer` combines project-root markers and exclusions from every supplied
implementation, assigning each file to its nearest discovered root. Although
`get_package_files()` is part of the metadata interface, the pipeline does not
currently use it.

### Source analysis

`extract_docstrings(source)` returns a tuple of docstring values for query
matching. `extract_imports(source, file_id)` returns `Import` records whose
`source_file_id` is the supplied file ID.

`resolve_imports(files, modules, imports)` receives indexed files, project roots,
and imports keyed by their positions in `Source.imports`. Return an
`ImportResolution` for each import, separating definite targets, ambiguous
candidates, and unresolved names. Target IDs must refer to the supplied files.
Resolution should not import or execute repository code.

See [Results and pipeline models](models.md) for the record fields.

### Tier rendering

Provide a declaration outline through `render_sigs(source)` and an outline
with retained documentation through `render_skel(source)`, leaving the
pipeline to supply full source for `FULL` and empty content for `TREE`.

`TierRenderer` handles token counting and reuses the next richer tier whenever
a compressed rendering is empty or larger, leaving budget enforcement outside
the language implementation.

See [Supported languages](../../guides/languages.md) for available support and
[Use a custom language](../../guides/adding-a-language.md) for a complete
application-side implementation.
