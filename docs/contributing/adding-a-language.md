# Contribute a language

This guide is for adding built-in support to ContextCraft. To supply an
implementation from your own application without changing ContextCraft, see
[Use a custom language](../guides/adding-a-language.md).

A language implementation connects file detection, source analysis, import
resolution, and tier rendering, as shown by `contextcraft/languages/python/`
and specified in the [language interface](../reference/api/language.md). Use
Python as the working example rather than the Rust package, which is currently
a placeholder.

## Add the package and grammar

Create `contextcraft/languages/<language>/` with `__init__.py` and `language.py`.
Use `queries.py` for Tree-sitter queries, and split extraction or import
resolution into separate modules when the implementation needs them. Follow the
Python package's responsibilities rather than copying every file.

If you need a grammar package, add it with `uv add <grammar-package>` and include
the updated `pyproject.toml` and `uv.lock`. Include
`from __future__ import annotations` in Python source files.

## Implement detection metadata

Subclass `contextcraft.languages.base.Language` and implement its static
methods. Choose a stable, distinct language ID, recognized suffixes and exact
filenames, project-root markers, package metadata filenames, and exclusion
globs. The [interface reference](../reference/api/language.md) lists the return
types for each method.

Because detection accepts the first case-sensitive suffix or filename match,
check for overlaps before choosing the implementation's registration order.
Root markers and exclusions from every configured language still apply during
indexing, even if no source files for that language are detected.

## Extract source metadata

The pipeline passes UTF-8 bytes, already redacted when that option is enabled.

- `extract_docstrings(source)` returns a tuple of docstring values used for
  query matching. Return an empty tuple if none are supported.
- `extract_imports(source, file_id)` returns `Import` records. Use the supplied
  file ID as `source_file_id`, and preserve the module name, relative level,
  and imported names needed by your resolver.

Handle incomplete source deliberately. For example, Python skips import
statements with parse errors rather than treating them as reliable imports.
Do not claim a syntax-error fallback that the implementation does not provide.

## Resolve imports without running source

`resolve_imports(files, modules, imports)` receives the indexed files, their
project roots, and imports keyed by position in `Source.imports`. Return one
`ImportResolution` per import and preserve those keys as `import_id`. Target
IDs must refer to the supplied files.

Keep ambiguous candidates and unresolved names separate from definite targets,
since only definite targets create graph edges. A possible attribute or
ambiguous module match must not be reported as a definite dependency, and
resolution must never execute repository code or import its modules.

Document the boundaries of the resolver. Python, for example, resolves within
each source file's project root and recognizes packages with `__init__.py` or
`__init__.pyi`, not namespace packages.

## Render useful outlines

Implement `render_sigs(source)` for a compact declaration outline and
`render_skel(source)` for declarations with retained documentation. Preserve
source order and enough nesting to make the result understandable. Outlines do
not need to be executable source.

The pipeline supplies `FULL` from loaded source and `TREE` as empty content.
`TierRenderer` counts tokens and reuses the next richer tier when an outline is
empty or larger. Do not implement budget allocation inside a language renderer.

## Register and exercise the implementation

To make the implementation built-in, import its class in
`contextcraft/languages/__init__.py` and add it to `BUILTIN_LANGUAGES`. No
separate registry is needed, because indexing records detected classes in
`Index.languages` for all later language-dependent stages to reuse.

Before changing the built-ins, exercise the class through the SDK's `languages`
argument. [Use a custom language](../guides/adding-a-language.md) explains how to
supply and replace implementations from application code.

Use a small sample repository to check detection, exclusions, and project-root
ownership. Inspect `source.imports`, resolutions, and graph edges to verify that
imports point where you expect. Read the actual `SIGS` and `SKEL` output, then
compile at a small budget and inspect the final artifact.

Include representative cases: nested declarations, multiline signatures,
Unicode, comments, incomplete syntax, aliases, relative imports, external
packages, and ambiguous local modules where the language supports them. State
unsupported cases in the pull request and update the
[supported-language guide](../guides/languages.md).
