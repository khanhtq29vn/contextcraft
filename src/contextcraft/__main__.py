from __future__ import annotations


def run_cli() -> None:
    """Application entry point."""
    from contextcraft.cli import app

    app()


if __name__ == "__main__":
    run_cli()
