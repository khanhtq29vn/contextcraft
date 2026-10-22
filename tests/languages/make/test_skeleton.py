from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_make_skeleton_keeps_recipes_on_separate_lines() -> None:
    language = default_registry().get("make")
    assert language is not None
    parsed = parse(b"build: input.c\n\tcc input.c\n", language)
    assert language.skeleton_builder(language.spec).build(parsed) == "build: input.c\n\t@:\n"
