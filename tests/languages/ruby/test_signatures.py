from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_ruby_endless_methods_keep_expression_body_syntax() -> None:
    language = default_registry().get("ruby")
    assert language is not None
    source = b"class Client\n def run(value) = service(value)\nend\n"
    parsed = parse(source, language)
    assert not parsed.has_errors
    signatures = language.signatures_builder(language.spec).build(parsed)
    assert signatures == "class Client\n    def run(value) = nil\nend\n"
