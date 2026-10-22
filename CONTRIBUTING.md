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
uv sync --all-extras --dev

# 3. Install pre-commit hooks
uv run pre-commit install
```

---

## 2. Running the Quality & Verification Suite

Before submitting a Pull Request, please ensure all three verification checks pass locally:

```bash
# 1. Lint & import sorting check
uv run ruff check src tests web benchmarks

# 2. Strict static type checking
uv run mypy src/contextcraft

# 3. Full test suite with branch coverage
uv run pytest --cov=contextcraft --cov-report=term-missing
```

---

## 3. High-Impact Ways to Contribute

1. **Adding or Enhancing Language Support (`src/contextcraft/scanner.py` & `ast_parser.py`):**
   - Map additional file extensions in `RepositoryScanner.EXTENSION_LANGUAGE_MAP`.
   - Add node types or docstring conventions in `UniversalASTParser`.
2. **Improving Cross-File Import Resolution (`src/contextcraft/graph.py`):**
   - Enhance `_resolve_imported_files` for Rust (`use crate::...`), Go, C/C++ `#include`, or Java package imports.
3. **Expanding Secret Detection Rules (`src/contextcraft/sanitizer.py`):**
   - Add zero-false-positive token regexes to `SecretSanitizer._TOKEN_PATTERNS`.

---

## 4. Pull Request Process

1. Create a descriptive feature branch (`git checkout -b feat/rust-use-resolver`).
2. Add unit tests in `tests/` covering your new functionality.
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat(ast): add Rust trait signature extraction`).
4. Push to your fork and open a Pull Request against `main`.