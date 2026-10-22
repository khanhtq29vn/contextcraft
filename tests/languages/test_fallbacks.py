from __future__ import annotations

from unittest.mock import patch

import pytest

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_missing_grammars_preserve_source(
    language_case: tuple[str, str, bytes, str, list[str]],
) -> None:
    language_id, _, source, _, _ = language_case
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
    ],
)
def test_incomplete_languages_preserve_source(language_id: str, source: bytes) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert parsed.has_errors
    assert language.skeleton_builder(language.spec).build(parsed) == source.decode()
    assert language.signatures_builder(language.spec).build(parsed) == source.decode()
