# Contributing to ContextCraft

First off, thank you for considering contributing to **ContextCraft**! Whether you are adding support for a new programming language grammar, refining the Personalized PageRank graph heuristics, or improving documentation, your contributions are deeply appreciated.

---

## 1. Quick Development Setup (Under 60 Seconds)

We use [Astral's `uv`](https://docs.astral.sh/uv/) for lightning-fast dependency management and virtual environments.

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/contextcraft.git
cd contextcraft

# 2. Create the virtual environment and install all dependencies (core + web + dev)
uv sync --locked --all-extras --dev

# 3. Install pre-commit hooks
uv run pre-commit install
```

---

## 2. Running the Quality & Verification Suite

Before submitting a Pull Request, please ensure all three verification checks pass locally:

```bash
# 1. Lint & import sorting check
uv run ruff check contextcraft tests web benchmarks

# 2. Strict static type checking
uv run mypy contextcraft

# 3. Full test suite with branch coverage
uv run pytest --cov=contextcraft --cov-report=term-missing
```

---

## Test Layout

- `tests/ast/`: AST models, parser behavior, and lexical scopes.
- `tests/languages/`: shared language conformance tests and per-language extraction, skeleton, and signature tests.
- `tests/pipeline/`: configuration, scanning, sanitization, ranking, optimization, elision, formatting, and token counting.
- `tests/integration/`: compiler, CLI, web API, and benchmark workflows.

Keep each test file focused on one component or behavior. Shared repository fixtures
live in `tests/conftest.py`; language samples and tokenizer fixtures live in their
subsystem's `conftest.py`. Pytest uses importlib mode so language folders can use
consistent filenames such as `test_extraction.py` and `test_skeleton.py`.

```bash
uv run pytest tests/languages/
uv run pytest tests/pipeline/test_optimizer.py
uv run pytest tests/integration/
```

## Documentation

The documentation uses Sphinx, Furo, and MyST Markdown. After installing the development dependencies, preview it with live reload:

```bash
uv run --locked sphinx-autobuild -b dirhtml docs docs/_build/html
```

Open <http://127.0.0.1:8000>. To build with warnings treated as errors:

```bash
uv run --locked sphinx-build -W --keep-going -b dirhtml docs docs/_build/html
```

---

## 3. High-Impact Ways to Contribute

1. **Adding or Enhancing Language Support (`contextcraft/languages/`):**
   - Follow the JavaScript package layout: `language.py`, `extraction.py`, `skeleton.py`, and `signatures.py`.
   - Declare parser IDs, extensions, filenames, and ignore patterns in `LanguageSpec`, then register the language in `languages/builtin.py`.
   - Implement extraction and the `SkeletonBuilder` / `SignaturesBuilder` classes. Register them as `skeleton_builder` and `signatures_builder` on the language class.
   - Test symbol ranges, syntax-safe summaries, missing grammars, and token-budget compliance.
2. **Improving Cross-File Import Resolution (`contextcraft/graph.py`):**
   - Enhance `_resolve_imported_files` for Rust (`use crate::...`), Go, C/C++ `#include`, or Java package imports.
3. **Expanding Secret Detection Rules (`contextcraft/sanitizer.py`):**
   - Add zero-false-positive token regexes to `SecretSanitizer._TOKEN_PATTERNS`.

---

## 4. Pull Request Process

1. Create a descriptive feature branch (`git checkout -b feat/rust-use-resolver`).
2. Add unit tests in `tests/` covering your new functionality.
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat(ast): add Rust trait signature extraction`).
4. Push to your fork and open a Pull Request against `main`.

---

## Releases

[Release Please](https://github.com/googleapis/release-please) opens or updates a release PR after pushes to `main`. It determines the next version from Conventional Commits:

- `fix:` and `perf:` produce patch releases.
- `feat:` produces minor releases.
- `BREAKING CHANGE:` footers or `!` produce minor releases while the version is `0.x`, and major releases after `1.0`.

The release PR updates `pyproject.toml`, `contextcraft/__init__.py`, `uv.lock`, `CHANGELOG.md`, and `.release-please-manifest.json`. Review it, wait for CI to pass, then merge it. The next workflow run creates a `v`-prefixed tag and a GitHub release. Use a conventional squash-merge title for normal PRs, and preserve the generated title and body when merging release PRs.

The manifest starts at the existing `v0.1.0` release. The configuration's `bootstrap-sha` limits the first release's commit history to changes after that tag; Release Please ignores it after the first release PR is merged.

### PyPI publishing

Merging a Release Please PR triggers a workflow run on `main`. When Release Please creates the tag and GitHub release, it calls **Publish to PyPI** with that tag. The publishing workflow builds the tagged source and publishes through the existing `pypi` environment and Trusted Publishing setup. Any environment approval rules still apply.

To publish an existing release manually, run **Actions → Publish to PyPI → Run workflow** from `main` and enter its tag, such as `v0.2.0`. Creating tags or releases manually does not trigger publishing; use this manual workflow instead.
