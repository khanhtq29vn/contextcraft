from __future__ import annotations

from unittest.mock import patch

import pytest

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


@pytest.mark.parametrize("language_id", ["ruby", "markdown", "protobuf", "elixir", "zig"])
def test_missing_grammars_preserve_source(
    language_sources: dict[str, bytes], language_id: str
) -> None:
    source = language_sources[language_id]
    language = default_registry().get(language_id)
    assert language is not None
    with patch("contextcraft.ast.parser.get_parser", side_effect=RuntimeError("unavailable")):
        parsed = parse(source, language)
    assert parsed.has_errors
    assert language.skeleton_builder(language.spec).build(parsed) == source.decode()
    assert language.signatures_builder(language.spec).build(parsed) == source.decode()


@pytest.mark.parametrize(
    "language_id,source",
    [
        ("ruby", b"class Client\n def run(value)\n"),
        ("php", b"<?php class Client { public function run("),
        ("swift", b"class Client { func run("),
        ("kotlin", b"class Client { fun run("),
        ("scala", b"class Client { def run("),
        ("lua", b"function run(value)\n"),
        ("r", b"run <- function(value) {"),
        ("bash", b"run() {"),
        ("elixir", b"defmodule Client do\n def run(value) do\n"),
        ("zig", b"pub fn run(value: i32) i32 {"),
    ],
)
def test_incomplete_languages_preserve_source(language_id: str, source: bytes) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert parsed.has_errors
    assert language.skeleton_builder(language.spec).build(parsed) == source.decode()
    assert language.signatures_builder(language.spec).build(parsed) == source.decode()
