from __future__ import annotations

import subprocess
import sys

import pytest

from contextcraft import __version__


def test_importing_entrypoint_does_not_run_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import contextcraft.__main__"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("command", ["contextcraft", "contextcraft-ai", None])
def test_entrypoint_version(command: str | None) -> None:
    args = [command] if command is not None else [sys.executable, "-m", "contextcraft"]
    result = subprocess.run([*args, "--version"], capture_output=True, text=True, check=True)

    assert result.stdout.strip() == f"contextcraft {__version__}"
