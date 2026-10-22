from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.javascript.language import JavaScriptLanguage


def test_signatures_keep_imports_public_classes_and_functions() -> None:
    source = b"""import {service} from "./service.js";
/** Public client. */
export class Client extends Base {
    /** Fetch a record. */
    fetch(id) {
        function internal() { return secret; }
        return service(id);
    }
    _helper() { return implementation; }
    #secret() { return implementation; }
}
export function run(value) { return service(value); }
const callback = value => service(value);
function _internal() { return implementation; }
register(value => service(value));
"""
    parsed = parse(source, JavaScriptLanguage)

    signatures = JavaScriptLanguage.signatures_builder(JavaScriptLanguage.spec).build(parsed)

    assert (
        signatures
        == """import {service} from "./service.js";
const Client = class Client extends Base {
    fetch(id) {}
};
const run = function run(value) {};
const callback = value => {};
"""
    )
    assert not get_parser("javascript").parse(signatures.encode()).root_node.has_error


def test_signatures_use_assigned_names_for_named_expressions() -> None:
    source = b"""
const run = function internal(value) { return internal(value); };
const Client = class InternalClient { fetch(id) { return service(id); } };
const _private = class Private { publicMethod() {} };
"""
    parsed = parse(source, JavaScriptLanguage)

    signatures = JavaScriptLanguage.signatures_builder(JavaScriptLanguage.spec).build(parsed)

    assert (
        signatures
        == """const run = function internal(value) {};
const Client = class InternalClient {
    fetch(id) {}
};
"""
    )
    assert not get_parser("javascript").parse(signatures.encode()).root_node.has_error
    assert {"internal", "InternalClient"} <= set(parsed.defined_identifiers)


def test_signatures_close_classes_before_other_declarations() -> None:
    source = b"""
class First { method() {} }
class Second { method() {} }
function run() {}
"""
    parsed = parse(source, JavaScriptLanguage)

    signatures = JavaScriptLanguage.signatures_builder(JavaScriptLanguage.spec).build(parsed)

    assert (
        signatures
        == """const First = class First {
    method() {}
};
const Second = class Second {
    method() {}
};
const run = function run() {};
"""
    )
    assert not get_parser("javascript").parse(signatures.encode()).root_node.has_error


def test_signatures_preserve_incomplete_source() -> None:
    source = b"function broken(value) { return value;"
    parsed = parse(source, JavaScriptLanguage)

    assert (
        JavaScriptLanguage.signatures_builder(JavaScriptLanguage.spec).build(parsed)
        == source.decode()
    )
