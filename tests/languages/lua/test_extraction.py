from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_lua_assigned_functions_keep_the_assigned_name() -> None:
    language = default_registry().get("lua")
    assert language is not None
    source = b"local run = function(value) return service(value) end\n"
    parsed = parse(source, language)
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].name == "run"
    signatures = language.signatures_builder(language.spec).build(parsed)
    assert "run = function(value)" in signatures
    assert not get_parser("lua").parse(signatures.encode()).root_node.has_error
