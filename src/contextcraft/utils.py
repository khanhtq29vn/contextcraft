from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    try:
        return version("contextcraft-ai")
    except PackageNotFoundError:
        return "0.0.0"
