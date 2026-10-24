from __future__ import annotations

import os
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import pathspec


def get_version() -> str:
    try:
        return version("contextcraft-ai")
    except PackageNotFoundError:
        return "0.0.0"


def matches_path_patterns(rel_path: str, patterns: list[str]) -> bool:
    """Match a POSIX relative path with gitignore-style patterns, like --include.

    A bare name matches at any depth, a "/" at the start or in the middle anchors
    to the repository root, a directory matches everything beneath it, "!" negates
    an earlier pattern, and backslash escapes work as in .gitignore. Beyond
    --include, a leading "./" also anchors to the root and, on Windows, "\\"
    separates paths (so escapes there need character classes such as "[[]").
    """
    lines = tuple(line for line in map(_normalize_pattern, patterns) if line)
    return bool(lines) and _path_spec(lines).match_file(rel_path)


_WINDOWS = os.sep == "\\"


def _normalize_pattern(pattern: str) -> str:
    # Trailing whitespace is ignored unless escaped, as in .gitignore.
    clean = pattern.rstrip()
    if clean.endswith("\\") and len(clean) < len(pattern):
        clean += " "
    if _WINDOWS:
        clean = clean.replace("\\", "/")
    negation = "!" if clean.startswith("!") else ""
    body = clean[len(negation) :]
    if body.startswith("./"):
        while body.startswith("./"):
            body = body[2:]
        body = "/" + body
    return negation + body if body.strip("/") else ""


@lru_cache(maxsize=64)
def _path_spec(lines: tuple[str, ...]) -> pathspec.PathSpec[Any]:
    return pathspec.PathSpec.from_lines("gitignore", lines)
