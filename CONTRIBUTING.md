# Contributing to ContextCraft

Contributions can improve language support, dependency resolution, ranking, token allocation, the Python bindings, or documentation. Keep changes focused and explain the behavior they affect.

## Development setup

Install these tools before working on the project:

- A current stable [Rust toolchain](https://rustup.rs/) with rustfmt and Clippy, plus a C/C++ toolchain for the Tree-sitter grammars.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10 or newer for the Python bindings and CLI.
- [Just](https://just.systems/man/en/) to run the project recipes.
- [dprint](https://dprint.dev/install/) for formatting and [Tombi](https://tombi-toml.github.io/tombi/docs/installation/) for TOML linting.
- Node.js 24 and the pnpm version declared in `package.json` if you are working on the docs.

Fork and clone the repository, then run these commands from its root:

```sh
git clone https://github.com/<your-username>/contextcraft.git
cd contextcraft
uv sync --locked --all-packages --extra cli --dev
cargo install plissken --locked
uv run --locked prek install
```

The Python installation builds the native extension through Maturin. Plissken generates the API documentation. Prek installs both pre-commit and pre-push hooks using `prek.toml`.

To see the available recipes:

```sh
just --list
```

## Repository layout

| Path                                   | Purpose                                                                                          |
| :------------------------------------- | :----------------------------------------------------------------------------------------------- |
| `crates/contextcraft_core/src/`        | Repository indexing, language analysis, dependency ranking, tier rendering, and token allocation |
| `crates/contextcraft_core/queries/`    | Tree-sitter capture queries                                                                      |
| `crates/contextcraft_core/tests/`      | Core integration tests and shared fixtures                                                       |
| `binding_python/src/`                  | PyO3 bindings                                                                                    |
| `binding_python/python/contextcraft/`  | Python exports, type stubs, and CLI                                                              |
| `binding_python/python/tests/`         | SDK and CLI tests using `unittest`                                                               |
| `docs/src/content/docs/`               | Documentation pages                                                                              |
| `docs/src/content/docs/reference/api/` | Generated API reference                                                                          |
| `.github/workflows/`                   | CI, documentation deployment, and releases                                                       |

## Formatting, linting, and tests

Run formatting through uv so the recipes can find Ruff in the workspace environment:

```sh
uv run --locked just fmt
uv run --locked just lint
just check-rust
just test-python
```

`fmt` changes files. `lint` runs Clippy and Tombi. `check-rust` checks Rust formatting, runs Clippy with warnings treated as errors, and runs workspace tests. `test-python` runs the SDK and CLI tests.

For Rust tests with all features enabled followed by the Python suite:

```sh
just test
```

Run Python type checking with the CLI dependencies available:

```sh
uv run --locked --package contextcraft-ai --extra cli --group dev pyrefly check binding_python/python/contextcraft
```

Pre-commit hooks run file checks, Ruff, Pyrefly, Rust formatting, and API generation when applicable. The pre-push hooks run Rust linting and tests for matching Rust or Cargo changes. To run the Rust pre-push checks manually:

```sh
uv run --locked prek run --hook-stage pre-push --all-files
```

Do not bypass a failed hook. Fix the cause and rerun it. If API generation changes files, review those changes and stage the generated output before retrying the commit.

### Targeted tests

Core integration tests cover indexing, language analysis, dependencies, ranking, redaction, tier rendering, formatting, and budget enforcement. Shared fixtures live in `crates/contextcraft_core/tests/common/`.

```sh
cargo test -p contextcraft-ai-core --test dependencies --locked
cargo test -p contextcraft-ai-core --test languages --locked
cargo test -p contextcraft-ai-core --test pipeline --locked
```

The Python suite checks configuration, snapshots, error mapping, token counts, CLI output, and entry points:

```sh
just test-python
```

## Python package builds

Build the source distribution and a wheel from it:

```sh
just build-python
```

Artifacts are written to `dist/`. To select an interpreter, set `UV_PYTHON` before running the recipe. CI uses this variable to select each Python version in its OS and interpreter matrix.

Changes to the native API should also update the Python exports and `.pyi` stubs in `binding_python/python/contextcraft/`.

## Documentation

The site uses Astro and Starlight. Install the frontend dependencies before starting it:

```sh
pnpm install --frozen-lockfile
just dev-docs
```

Use the URL printed by Astro. The site uses the `/contextcraft/` base path for GitHub Pages.

Build the site with:

```sh
just build-docs
```

This builds the existing documentation into `docs/dist/`. It does not regenerate the API reference. After changing Rust or Python API documentation, run:

```sh
just gen-docs
```

Review and include the generated changes, but do not edit generated API pages or `_sidebar.mjs` by hand. Their source and output paths are configured in `plissken.toml`.

CI builds the docs on pull requests. Successful CI runs on `main` upload the site and deploy it through `.github/workflows/deploy-docs.yml`. The repository's Pages source must be set to **GitHub Actions**.

## Language and pipeline changes

To add or extend a language:

1. Implement or update its `Language` implementation in `crates/contextcraft_core/src/languages/` and its capture query in `crates/contextcraft_core/queries/`.
2. For a new grammar, add its dependency to the Cargo workspace and core crate. Export the module in `languages.rs` and register the implementation in `index.rs`.
3. Define filename detection, source extensions, exclusions, outline captures, and any supported local dependency or package resolution.
4. Check declaration ranges, outline content, dependency edges, and token-budget behavior with representative source files.
5. Update the [language support reference](docs/src/content/docs/reference/languages.md) and regenerate API documentation when needed.

Dependency resolution is static and repository-local. Document unsupported constructs rather than implying compiler-level name binding or executing project build scripts.

Ranking changes belong in `graph/scorer.rs`, allocation changes in `optimizer.rs`, and final serialization and budget correction in `formatter.rs`. Secret redaction is configured in `repo.rs` before source analysis. Preserve byte offsets and line breaks when changing redaction behavior.

## Pull requests

- Open PRs against `main` and describe the problem, changed behavior, and checks you ran.
- Keep unrelated cleanup, build output, and temporary artifacts out of the diff.
- Include regression coverage for behavior changes and update affected documentation.
- Use [Conventional Commits](https://www.conventionalcommits.org/), such as `fix(rust): resolve local module aliases`, for commit messages and squash-merge titles.
- Wait for the full CI matrix to pass before merging. Local checks cannot verify every supported platform.

## AI-assisted contributions

AI-assisted contributions are welcome. You are responsible for the code you submit, whether you wrote it yourself or used an assistant.

Read every change before submitting it and make sure you understand what the code does. You should be able to explain why the change is needed, how it fits the pipeline, and how it handles relevant edge cases. Run the checks yourself and inspect the results rather than relying on an assistant's claim that they passed.

Do not submit generated code you have not reviewed or cannot explain. Verify that referenced APIs, dependencies, and commands exist, and check generated examples against the actual implementation. The same review standard applies to code, documentation, and configuration.

## Releases

[Release Please](https://github.com/googleapis/release-please) opens or updates a release PR after pushes to `main`. Conventional Commits determine the version:

- `fix:` and `perf:` produce patch releases.
- `feat:` produces minor releases.
- `BREAKING CHANGE:` footers or `!` produce minor releases while the version is `0.x`, and major releases after `1.0`.

Rust and Python share the version in `[workspace.package]` in `Cargo.toml`. Both Rust crates inherit it, and Maturin reads the binding crate's version for the Python distribution. Release Please uses the `simple` strategy with explicit TOML updates for `Cargo.toml` and the workspace package entries in `Cargo.lock`.

Review the release PR's versions, changelog, and `.release-please-manifest.json`, then wait for CI before merging. Preserve the generated release PR title and body. The next Release Please run creates a `v`-prefixed tag and a GitHub release. The manifest tracks the last released version, and `bootstrap-sha` only applies before the first release PR is merged.

### PyPI publishing

When Release Please creates a release, `.github/workflows/release-please.yml` dispatches **Publish to PyPI** on `main` with the release tag. The publishing workflow builds the tagged source, then publishes `contextcraft-ai` through the `pypi` environment using Trusted Publishing. The Python import remains `contextcraft`.

Maturin builds Python 3.10+ ABI3 wheels for Linux x86_64 and ARM64, macOS Intel and Apple Silicon, and Windows x86_64 and ARM64. ARM64 wheels must pass an installation and tokenizer smoke test before publishing. A source distribution includes the Rust workspace. Rust crates are not published to crates.io.

PyPI publishing runs in its own top-level workflow so its attestation identity matches the configured Trusted Publisher, `publish-pypi.yml`. Any required `pypi` environment approval must be granted before publication.

To publish an existing release manually, run **Actions → Publish to PyPI → Run workflow** from `main` and enter a tag containing the Maturin packaging configuration. Creating a tag or release manually does not trigger publication.
