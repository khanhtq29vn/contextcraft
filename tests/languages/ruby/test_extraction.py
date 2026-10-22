from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_ruby_first_method_documentation_is_extracted() -> None:
    language = default_registry().get("ruby")
    assert language is not None
    source = b"class Client\n # Run documentation.\n def run(value)\n service(value)\n end\nend\n"
    parsed = parse(source, language)
    method = next(symbol for symbol in parsed.symbols if symbol.name == "run")
    assert method.docstring_range is not None
    assert parsed.text(method.docstring_range) == "# Run documentation."
