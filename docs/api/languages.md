# Language Extension API

## Selecting languages

`contextcraft.languages.BUILTIN_LANGUAGES` is a tuple of language classes.
Currently it contains only `PythonLanguage`. Rust has no registered implementation.

Pass a replacement tuple to `ContextCraft` or `Indexer` to select implementations.
The tuple replaces the defaults; extend `BUILTIN_LANGUAGES` to keep them.

```python
from contextcraft import ContextCraft
from contextcraft.config import Config
from contextcraft.languages.python.language import PythonLanguage

compiler = ContextCraft(Config(budget_tokens=8000), languages=(PythonLanguage,))
artifact = compiler.compile(".")
```

There is no separate registry or alias API. Implementations should use distinct
language IDs. Detection chooses the first class in tuple order whose suffix or
exact filename matches the path. Both checks are case-sensitive; an exact
filename match does not take priority over an earlier suffix match.

Indexing stores detected implementations in `Index.languages`, keyed by language
ID, and records each file's language ID in `File.language_id`. Later stages reuse that
mapping. A non-null file language ID requires a matching implementation;
missing entries raise `KeyError` when used. Files with no match have
`language_id=None` and retain full source without language-specific analysis.

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

`Indexer` uses metadata from every supplied implementation for project-root
markers and exclusions. It assigns each file to the nearest discovered root.
`get_package_files()` is available as metadata but is not currently used by the
pipeline.

### Source analysis

`extract_docstrings(source)` returns a tuple of docstring values for query
matching. `extract_imports(source, file_id)` returns `Import` records whose
`source_file_id` is the supplied file ID.

`resolve_imports(files, modules, imports)` receives indexed files, project roots,
and imports keyed by their positions in `Source.imports`. Return an
`ImportResolution` for each import, separating definite targets, ambiguous
candidates, and unresolved names. Target IDs must refer to the supplied files.
Resolution should not import or execute repository code.

See [Results and Pipeline Models](models.md) for the record fields.

### Tier rendering

`render_sigs(source)` returns a declaration outline. `render_skel(source)`
returns an outline with retained documentation. The pipeline supplies full
source for `FULL` and empty content for `TREE`.

`TierRenderer` handles token counting and fallback. If a compressed rendering
is empty or larger than the next richer tier, that richer tier is reused.
Implementations do not need to enforce the output budget.

## Python implementation

```{eval-rst}
.. autoclass:: contextcraft.languages.python.language.PythonLanguage
```

Python detection recognizes `.py`, `.pyi`, and `.pyw`, plus `SConstruct`,
`SConscript`, and `wscript`. Analysis and rendering use Tree-sitter.

- Docstring extraction returns literal module, class, and function docstrings
  in source order. Invalid captures and non-string values are skipped.
- Import extraction includes nested imports, preserves relative-import levels,
  and records original names rather than aliases. Statements with parse errors
  are skipped.
- Import resolution stays within the source file's project root. It recognizes
  packages with `__init__.py` or `__init__.pyi`, not namespace packages. A `.py`
  module takes precedence over a matching `.pyi` stub. Names that could be
  attributes rather than submodules may remain unresolved.
- `SIGS` includes class and function headers, including nested and private
  declarations. It omits decorators, docstrings, imports, and bodies.
- `SKEL` includes headers, decorators, and captured class/function docstrings.
  It omits imports and implementation bodies.

Python's `render_sigs()` and `render_skel()` accept an optional Python-configured
`tree_sitter.Parser` as a second argument for reuse. Other language
implementations need only accept the source argument defined by `Language`.
