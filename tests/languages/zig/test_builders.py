from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import ZigLanguage


def test_zig_summaries_keep_public_containers_fields_and_reexports() -> None:
    source = (
        'pub const service = @import( "service.zig" );\r\n'
        "/// Client café documentation.\r\npub const Client = struct {\r\n"
        " value: i32,\r\n pub fn run(value: i32) i32 { return service.run(value); }\r\n"
        " fn secret() i32 { return 42; }\r\n};\r\n"
        "pub const Status = enum { ready, done };\r\n"
        "pub const Result = union(enum) { value: i32, empty };\r\n"
        "pub const enabled = true;\r\npub extern fn external(value: i32) void;\r\n"
        "export fn entry() void { service.start(); }\r\n"
    ).encode()
    parsed = parse(source, ZigLanguage)
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}
    skeleton = ZigLanguage.skeleton_builder(ZigLanguage.spec).build(parsed)
    signatures = ZigLanguage.signatures_builder(ZigLanguage.spec).build(parsed)

    assert not parsed.has_errors
    assert {
        "Client",
        "Client.value",
        "Client.run",
        "Client.secret",
        "Status",
        "Status.ready",
        "Status.done",
        "Result.empty",
        "entry",
        "enabled",
        "external",
    } <= set(symbols)
    docstring = symbols["Client"].docstring_range
    assert docstring is not None
    assert "Client café documentation." in parsed.text(docstring)
    assert "Client café documentation." in skeleton
    assert "service.run(value)" not in skeleton
    assert "pub const Client = struct" in signatures
    assert "value: i32," in signatures
    assert "pub fn run(value: i32) i32" in signatures
    assert "pub extern fn external(value: i32) void;" in signatures
    assert "export fn entry() void {}" in signatures
    assert "ready," in signatures
    assert "empty" in signatures
    assert all(
        binding.scope.kind == "enum"
        for binding in parsed.scope_graph.bindings
        if binding.name in {"ready", "done"}
    )
    assert signatures.count('@import( "service.zig" )') == 1
    assert "secret" not in signatures
    assert not parse(skeleton.encode(), ZigLanguage).has_errors
    assert not parse(signatures.encode(), ZigLanguage).has_errors
    assert parsed.source == source


def test_zig_imports_ignore_dynamic_arguments_and_string_contents() -> None:
    source = b'const service = @import( "service.zig" );\nconst dynamic = @import(module_name);\nconst text = "@import(ignored)";\n'
    parsed = parse(source, ZigLanguage)

    assert not parsed.has_errors
    assert [item.module for item in parsed.imports] == ["service.zig"]
