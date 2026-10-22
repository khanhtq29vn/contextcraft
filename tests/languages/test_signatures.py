from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


@pytest.mark.parametrize(
    "language_id,source",
    [
        (
            "php",
            b"<?php\nclass Client {\n private function secret() { return 1; }\n public function run() { return 2; }\n}\n",
        ),
        (
            "swift",
            b"class Client {\n private func secret() -> Int { return 1 }\n func run() -> Int { return 2 }\n}\n",
        ),
        (
            "kotlin",
            b"class Client {\n private fun secret(): Int { return 1 }\n fun run(): Int { return 2 }\n}\n",
        ),
        (
            "scala",
            b"class Client {\n private def secret(): Int = { 1 }\n def run(): Int = { 2 }\n}\n",
        ),
    ],
)
def test_native_signatures_exclude_private_methods(language_id: str, source: bytes) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert not parsed.has_errors
    signatures = language.signatures_builder(language.spec).build(parsed)
    assert "run" in signatures
    assert "secret" not in signatures
    assert not get_parser(language.spec.parser_id).parse(signatures.encode()).root_node.has_error
