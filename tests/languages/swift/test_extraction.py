from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_swift_structs_enums_and_initializers() -> None:
    language = default_registry().get("swift")
    assert language is not None
    source = b"struct Client { init(value: Int) { work(value) }\n deinit { cleanup() }\n}\nenum State { case ready }\n"
    parsed = parse(source, language)
    assert not parsed.has_errors
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}
    assert symbols["Client"].kind == "struct"
    assert symbols["State"].kind == "enum"
    assert symbols["Client.init"].kind == "method"
    assert symbols["Client.deinit"].kind == "method"
    skeleton = language.skeleton_builder(language.spec).build(parsed)
    assert "work(value)" not in skeleton
    assert "cleanup()" not in skeleton
    assert "case ready" in skeleton
    assert not get_parser("swift").parse(skeleton.encode()).root_node.has_error
