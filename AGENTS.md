# Agent Development Guide

A file for [guiding coding agents](https://agents.md/).

## Commands

Run commands from the repository root.

- Setup: `just init`; `pnpm install` for docs dependencies.
- Formatting: `uv run --locked just fmt`.
- Linting: `uv run --locked just lint`.
- Rust checks (formatting, Clippy, tests): `just check-rust`.
- All tests: `just test`.
- Individual test suites: `just test-rust`, `just test-python`.
- Python package build: `just build-python`.
- Generate API docs: `just gen-docs`.
- Docs development: `just dev-docs`.
- Docs build: `just build-docs`.
- List recipes: `just --list`.

## Coding Conventions

- Adding empty line between block or a group of code improves readability.
- Only adding tests when explicitly requested.
