from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import JavaLanguage


def test_java_records_and_constructors_keep_package_and_hide_private_members() -> None:
    source = b"""package demo;
import app.Service;
/** Client documentation. */
public record Client(int value) {
    public Client { validate(value); }
    public Client(String value) { this(Service.parse(value)); }
    private Client() { this(0); }
    private int secret() { return 42; }
    public int _public() { return value; }
    public int run(int value) { return Service.run(value); }
}
"""
    parsed = parse(source, JavaLanguage)
    constructors = [symbol for symbol in parsed.symbols if symbol.kind == "constructor"]
    skeleton = JavaLanguage.skeleton_builder(JavaLanguage.spec).build(parsed)
    signatures = JavaLanguage.signatures_builder(JavaLanguage.spec).build(parsed)

    assert not parsed.has_errors
    assert len(constructors) == 3
    assert all(
        symbol.parent is not None and symbol.parent.name == "Client" for symbol in constructors
    )
    assert "Client documentation." in skeleton
    assert "validate(value)" not in skeleton
    assert "Service.parse(value)" not in skeleton
    assert signatures.startswith("package demo;")
    assert "public record Client(int value)" in signatures
    assert "public Client {}" in signatures
    assert "public Client(String value) {}" in signatures
    assert "_public" in signatures
    assert "private" not in signatures
    assert "secret" not in signatures
    assert not parse(skeleton.encode(), JavaLanguage).has_errors
    assert not parse(signatures.encode(), JavaLanguage).has_errors
    for reference in parsed.scope_graph.references:
        if reference.name == "value" and reference.scope.kind == "constructor":
            assert reference.scope.resolve("value") is not None
    assert parsed.source == source
