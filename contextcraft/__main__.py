"""Run the ContextCraft command-line interface."""

from __future__ import annotations


def run_cli() -> None:
    """Load the optional CLI dependencies and run the command-line app."""
    from contextcraft.cli import run_cli as cli_run

    cli_run()


if __name__ == "__main__":
    run_cli()
