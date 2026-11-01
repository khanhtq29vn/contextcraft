_default:
  @just --list -u

init:
  uv sync --all-packages --extra cli --dev
  cargo install plissken

build-python:
  uv build --package contextcraft-ai --out-dir dist

check-rust: check-rust-format lint-rust test-rust

check-rust-format:
  cargo fmt --all -- --check

lint-rust:
  cargo clippy --workspace --all-targets --locked -- -D warnings

test-rust:
  cargo test --workspace --locked

gen-docs:
  plissken render

dev-docs:
  pnpm --filter @contextcraft-ai/docs dev

build-docs:
  pnpm --filter @contextcraft-ai/docs build

fmt:
  cargo fmt
  dprint fmt
  ruff check --select I --fix .
  ruff format .

lint:
  cargo lint
  tombi lint

test-python:
  uv run --locked --package contextcraft-ai --extra cli python -m unittest discover -s binding_python/python/tests -v

test:
  cargo test --workspace --all-features --locked
  just test-python
