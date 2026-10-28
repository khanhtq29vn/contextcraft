# Supported languages

Each built-in language implementation connects file detection with import
analysis and source outlines, while files without a matching implementation
can still be included as UTF-8 text without language-aware analysis.

## Available languages

| Language | ID       | Suffixes              | Exact filenames                       |
| :------- | :------- | :-------------------- | :------------------------------------ |
| Python   | `python` | `.py`, `.pyi`, `.pyw` | `SConstruct`, `SConscript`, `wscript` |

## Detection

Detection checks file suffixes and exact filenames case-sensitively, choosing
the first matching implementation in the configured language tuple. It neither
inspects shebangs nor tries several parsers, so an earlier suffix match takes
priority even if a later implementation matches the exact filename.

A file with no matching implementation receives `language_id=None`, and its
compressed tiers reuse the loaded source after any enabled redaction.

## Outlines and import analysis

Each implementation decides what to retain in its outlines: `SIGS` provides a
compact view of declarations, while `SKEL` can preserve more structure and
documentation. Neither needs to be executable source. The renderer reuses the
next richer tier whenever an outline is empty or larger, but leaves
syntax-error handling to the language implementation.

Import resolution can produce a definite target, a set of ambiguous
candidates, or an unresolved name, with only definite targets contributing
dependency edges. The forms a resolver understands depend on the language, so
support for detection and outlines does not imply that every import can be
resolved.

## Exclusions and skipped sources

During indexing, exclusions from every configured language apply alongside Git
ignore rules and explicit exclude patterns, even when the scan finds no source
files for that language. These exclusions can cover generated files, caches,
lockfiles, and build artifacts, and remain active with `--no-gitignore`. The
scanner does not load `.contextignore` as a custom ignore file.

Files that exceed the size limit, contain binary control bytes, or cannot be
decoded as UTF-8 remain indexed with only a `TREE` tier, whereas empty UTF-8
files are still eligible for loading. Because the path listing has its own
budget, even an indexed file may have no visible entry in the final artifact.

## Extend support

To supply an implementation from your application, follow [Use a custom
language](adding-a-language.md) and consult the [language
interface](../reference/api/language.md) for the API contract. Adding it to
ContextCraft's built-ins is a separate process covered in [Contribute a
language](../contributing/adding-a-language.md).
