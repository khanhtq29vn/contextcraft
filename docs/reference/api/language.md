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
   :members: get_language_id, get_file_extensions, get_filenames, get_root_files, get_package_files, get_ignore_patterns, analyze, resolve_imports, render_sigs, render_skel
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

Implement `analyze(source, file_id)` to return a `FileAnalysis` containing
`docstrings`, `imports`, and outline spans in `sigs` and `skel`. The loader calls
this method once per recognized file. Python uses one parse and one combined
query pass.

Each outline span is `(start_byte, end_byte, indentation)`. Return spans in
source order without duplicates, using offsets into the supplied UTF-8 bytes.
Do not retain Tree-sitter nodes or trees.

```{eval-rst}
.. autoclass:: contextcraft.models.FileAnalysis
```

Set `docstrings` to a tuple of extracted values for query matching, and
`imports` to a tuple of `Import` records whose `source_file_id` is the supplied
file ID. Use empty tuples when these metadata are not supported.

This replaces the separate `extract_docstrings()` and `extract_imports()`
language methods. Custom implementations must provide `analyze()`.

`resolve_imports(files, modules, imports)` receives indexed files, project roots,
and imports keyed by their positions in `Source.imports`. Return an
`ImportResolution` for each import, separating definite targets, ambiguous
candidates, and unresolved names. Target IDs must refer to the supplied files.
Resolution should not import or execute repository code.

See [Results and pipeline models](models.md) for the record fields.

### Tier rendering

`render_sigs(source, analysis)` and `render_skel(source, analysis)` render the
stored spans against the analyzed source bytes. Both have default
implementations; override them only for language-specific output formatting,
without parsing or querying again. The analysis argument is required, and
rendered text is not cached.

```python
analysis = PythonLanguage.analyze(source, file_id)
signatures = PythonLanguage.render_sigs(source, analysis)
skeleton = PythonLanguage.render_skel(source, analysis)
```

The pipeline supplies full source for `FULL` and empty content for `TREE`.

`TierRenderer` handles token counting and reuses the next richer tier whenever
a compressed rendering is empty or larger, leaving budget enforcement outside
the language implementation.

See [Supported languages](../../guides/languages.md) for available support and
[Use a custom language](../../guides/adding-a-language.md) for a complete
application-side implementation.
