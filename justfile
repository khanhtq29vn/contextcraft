_default:
    @just --list -u

init:
    uv sync --all-extras

fmt:
    uv run ruff check --select I --fix . && uv run ruff format .
    dprint fmt

lint:
    uv run ruff check
    uv run pyrefly check

build:
    uv build

build-docs *args:
    uv run --extra docs sphinx-build -b dirhtml docs docs/_build/html {{args}}

preview-docs:
    uv run --extra docs sphinx-autobuild -b dirhtml docs docs/_build/html
