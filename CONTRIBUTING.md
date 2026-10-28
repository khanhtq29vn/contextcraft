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
changes, show the expected result and relevant failure cases. Lint and type
checks alone cannot establish that the behavior is correct.

For CLI changes, inspect the help output and run the command on a small sample:

```bash
uv run contextcraft --help
uv run contextcraft path/to/sample-repo --budget 8000 --format json -o /tmp/context.json
```

Check that the artifact contains the expected files and that its reported token
count fits the budget. If counting falls back to estimates, the exact-budget
guarantee does not apply.

## Adding a language

Follow [Contribute a language](docs/contributing/adding-a-language.md) for the package layout,
metadata methods, import-resolution contract, tier rendering, registration, and
sample cases to check. The [language interface](docs/reference/api/language.md)
lists the method signatures and return types.

State unsupported syntax and resolution limits in your pull request, and update
[Supported languages](docs/guides/languages.md) when adding built-in support.

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
and inspect the results rather than relying on an assistant's claim that they
passed.

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
apply. Release Please reports whether dispatch succeeded. To confirm that publishing
succeeded, check the separate **Publish to PyPI** run.

To publish an existing release manually, open **Actions → Publish to PyPI → Run
workflow** on `main` and enter the tag, such as `v0.2.0`. Creating a tag or release
manually does not trigger publishing.
