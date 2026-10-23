from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.javascript.language import JavaScriptLanguage


def test_parser_extracts_javascript_symbols_and_imports() -> None:
    source = b"""import {service} from "./service.js";
/** Public service. */
export class Client extends Base {
    /** Fetch a record. */
    async fetch(id) { return service(id); }
}
export const run = (value) => service(value);
"""
    parsed = parse(source, JavaScriptLanguage)
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}

    assert set(symbols) == {"Client", "Client.fetch", "run"}
    assert symbols["Client"].kind == "class"
    assert symbols["Client"].body_range is not None
    class_docstring = symbols["Client"].docstring_range
    assert class_docstring is not None
    assert parsed.text(class_docstring) == "/** Public service. */"
    assert symbols["Client.fetch"].kind == "method"
    assert symbols["Client.fetch"].parent is symbols["Client"]
    assert parsed.text(symbols["Client.fetch"].signature_range) == "async fetch(id)"
    method_docstring = symbols["Client.fetch"].docstring_range
    assert method_docstring is not None
    assert parsed.text(method_docstring) == "/** Fetch a record. */"
    span = symbols["Client.fetch"].body_range
    assert span is not None
    assert source[span.start_byte : span.end_byte] == b"{ return service(id); }"
    assert [item.module for item in parsed.imports] == ["./service.js"]
    assert [parsed.text(item.declaration_range) for item in parsed.imports] == [
        'import {service} from "./service.js";'
    ]
    assert {"Client", "Client.fetch", "service", "run", "id", "value"} <= set(
        parsed.defined_identifiers
    )
    assert set(parsed.referenced_identifiers) == {"Base", "service", "id", "value"}


def test_parsed_ast_retains_source_ranges_and_anonymous_symbol_parents() -> None:
    source = b"register(function (arg) { return () => arg; });"
    parsed = parse(source, JavaScriptLanguage)
    outer, inner = parsed.symbols

    assert parsed.source == source
    assert outer.name is None
    assert inner.name is None
    assert outer.parent is None
    assert inner.parent is outer
    assert outer.qualified_name is None
    assert inner.qualified_name is None
    assert parsed.text(outer.declaration_range) == "function (arg) { return () => arg; }"
    assert parsed.text(outer.signature_range) == "function (arg)"
    assert parsed.text(inner.signature_range) == "() =>"
    assert inner.body_range is not None
    assert parsed.text(inner.body_range) == "arg"
