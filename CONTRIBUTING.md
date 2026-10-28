# Contributing to ContextCraft

Contributions can improve language support, import resolution, ranking, secret
redaction, or documentation. Keep each pull request focused on one change and
explain how you checked it.

## Development setup

Install [uv](https://docs.astral.sh/uv/), [just](https://just.systems/), and
[dprint](https://dprint.dev/). Then fork and clone the repository:

```bash
git clone https://github.com/<your-username>/contextcraft.git
cd contextcraft
just init
```

`just init` creates the virtual environment and installs the project, development
dependencies, and all optional extras. Read [AGENTS.md](AGENTS.md) for the project
conventions, including guidance for coding agents.

## Checks before submitting

```bash
just fmt
just lint
just build
```

`just fmt` sorts Python imports and formats Python with Ruff, then runs dprint.
`just lint` runs Ruff and Pyrefly. `just build` creates the source distribution
and wheel in `dist/`.

The architecture rewrite currently has no automated test suite. Include a
reproducible example and the checks you ran in your pull request. For behavior
changes, show the expected result and any relevant failure cases; passing lint
and type checks alone does not establish that the behavior is correct.

For CLI changes, inspect the help output and run the command on a small sample:

```bash
uv run contextcraft --help
uv run contextcraft path/to/sample-repo --budget 8000 --format json -o /tmp/context.json
```

Check that the artifact contains the expected files and that its reported token
count fits the budget. If counting falls back to estimates, the exact-budget
guarantee does not apply.

## Adding a language

### 1. Add the package and grammar

Create `contextcraft/languages/<language>/` with an `__init__.py` and a
`language.py`. Put Tree-sitter queries in `queries.py` and split import
extraction, resolution, or docstring handling into separate modules when needed.
The Python package shows this layout; you do not need to copy every file.

If the implementation uses a new Tree-sitter grammar package, add it with
`uv add <grammar-package>` and include the updated `pyproject.toml` and `uv.lock`
in the pull request. Include `from __future__ import annotations` in Python
source files.

### 2. Define detection and project metadata

Implement a subclass of `contextcraft.languages.base.Language`. All methods on
that interface are static methods. Supply these metadata methods:

| Method                  | What to return                                                                |
| :---------------------- | :---------------------------------------------------------------------------- |
| `get_language_id()`     | A stable ID distinct from other implementations                               |
| `get_file_extensions()` | A frozen set of suffixes with leading dots, such as `.rs`                     |
| `get_filenames()`       | A frozen set of exact filenames to recognize                                  |
| `get_root_files()`      | A frozen set of filenames that identify project roots                         |
| `get_package_files()`   | A frozen set of package, dependency, and environment filenames                |
| `get_ignore_patterns()` | A tuple of exclusion globs for generated files, caches, and similar artifacts |

Detection is case-sensitive. The first matching implementation in the supplied
language tuple wins, whether it matches a suffix or an exact filename. Check
for overlaps with existing implementations before choosing the registration
order. Package-file metadata is part of the interface but is not currently used
by the pipeline.

### 3. Extract metadata and resolve imports

Implement the analysis methods using UTF-8 source bytes. Source loading applies
redaction before calling them when redaction is enabled.

- `extract_docstrings(source)` returns a tuple of docstring values for query
  matching. Return an empty tuple if the language has no supported docstrings.
- `extract_imports(source, file_id)` returns `Import` records. Set each record's
  `source_file_id` to the supplied ID and preserve the information needed to
  resolve relative imports and imported names.
- `resolve_imports(files, modules, imports)` returns one `ImportResolution` per
  import. The input mapping keys are positions in `Source.imports`; preserve
  those keys as `import_id`. Target file IDs must come from the supplied index.

Keep definite targets separate from ambiguous candidates and unresolved names.
Only definite targets become dependency edges. Do not guess a target when the
syntax could refer to an attribute, an external dependency, or several local
files. Resolve imports without executing repository code or importing its
modules.

### 4. Render signatures and skeletons

Implement `render_sigs(source)` for a compact declaration outline and
`render_skel(source)` for an outline that retains relevant documentation. Keep
source order and enough nesting information to make declarations understandable.
The output does not have to be executable code.

The pipeline supplies `FULL` from the loaded source and `TREE` as empty content.
`TierRenderer` counts tokens and reuses the next richer tier if a compressed
rendering is empty or larger. Language implementations should not allocate the
output budget themselves.

### 5. Register and check the implementation

Import the language class in `contextcraft/languages/__init__.py` and add it to
`BUILTIN_LANGUAGES`. Indexing puts detected classes in `Index.languages`; source
loading, import resolution, ranking, and tier rendering all reuse that mapping.
There is no separate registry to update.

During development, you can use `ContextCraft(languages=(YourLanguage,))` or
`Indexer(languages=(YourLanguage,))` without changing the built-ins. This replaces
the default language set rather than extending it.

Use a small sample repository to check:

- Extension and exact-filename detection, project-root ownership, and exclusions.
- Declarations with decorators or attributes, nested declarations, multiline
  signatures, comments, Unicode, and incomplete or invalid syntax.
- Absolute and relative imports, aliases, grouped imports, unresolved external
  dependencies, and ambiguous local targets where the language supports them.
- The actual `SIGS` and `SKEL` content, not just whether rendering completes.
- End-to-end output at a small budget, including the formatter's final count.

Describe unsupported syntax and resolution limits in the pull request. Update
`docs/api/languages.md` and any affected language-support documentation rather
than implying support that has not been implemented.

## Other changes

Import resolution is dispatched by `contextcraft/imports.py`, with
language-specific logic in each language package. Dependency graph construction
and ranking live in `contextcraft/graph.py`. Secret recognition and masking live
in `contextcraft/source.py`.

For redaction changes, check both secrets that should be masked and ordinary
text that should remain untouched. Masking must preserve byte offsets and line
endings so later parsing still refers to the loaded source correctly.

## Documentation

The docs use Sphinx, MyST Markdown, Furo, and KaTeX. Preview them with live reload:

```bash
just preview-docs
```

Open <http://127.0.0.1:8000>. Before submitting documentation changes, build with
warnings treated as errors:

```bash
just build-docs -E -W --keep-going
```

The generated HTML is in `docs/_build/html/`. Update public API docstrings when
behavior changes, and keep examples consistent with the current CLI and SDK.

## AI-assisted contributions

AI-assisted contributions are welcome. You are responsible for the code you
submit, whether you wrote it yourself or used an assistant.

Read every change before submitting it and make sure you understand what the
code does. You should be able to explain why the change is needed, how it fits
the pipeline, and how it handles relevant edge cases. Run the checks yourself
and inspect the results; do not rely on an assistant's claim that they passed.

Do not submit generated code you have not reviewed or cannot explain. Verify
that referenced APIs, dependencies, and commands exist, and check generated
examples against the actual implementation. The same review standard applies
to code, documentation, and configuration.

## Pull requests

1. Create a descriptive feature branch, such as `feat/rust-use-resolver`.
2. Keep the diff focused. Describe the problem, the approach, any limitations,
   and the examples or checks used to verify the result.
3. Run the relevant checks above and update documentation for changed behavior.
4. Use [Conventional Commits](https://www.conventionalcommits.org/), for example
   `feat(languages): add Rust import resolution`.
5. Push to your fork and open a pull request against `main`.

## Releases

[Release Please](https://github.com/googleapis/release-please) opens or updates a
release pull request after pushes to `main`. It uses Conventional Commits to
choose the next version:

- `fix:` and `perf:` produce patch releases.
- `feat:` produces minor releases.
- `BREAKING CHANGE:` footers or `!` produce minor releases while the version is
  `0.x`, and major releases after `1.0`.

The release pull request updates the package version, lockfile, changelog, and
release manifest. Review it, wait for CI, and merge it without changing the
generated title or body. The next workflow run creates a `v`-prefixed tag and a
GitHub release. Use a conventional squash-merge title for other pull requests.

### PyPI publishing

When Release Please creates a release, it dispatches **Publish to PyPI** on
`main` with the release tag. That workflow builds the tagged source and publishes
through the `pypi` environment using Trusted Publishing and attestations. The
separate workflow keeps the attestation identity aligned with the configured
PyPI Trusted Publisher, `publish-pypi.yml`. Any environment approval rules still
apply. Release Please reports whether dispatch succeeded; check the separate
**Publish to PyPI** run to confirm the publishing result.

To publish an existing release manually, open **Actions → Publish to PyPI → Run
workflow** on `main` and enter the tag, such as `v0.2.0`. Creating a tag or release
manually does not trigger publishing.
