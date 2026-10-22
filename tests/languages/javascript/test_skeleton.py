from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.ast.parser import parse
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.javascript.skeleton import SkeletonBuilder


def test_skeleton_uses_only_the_structural_summary() -> None:
    source = b"function run() { return result; }"
    body_start = source.index(b"{")
    parsed = ParsedAst(
        source=source,
        symbols=[
            Symbol(
                name="run",
                kind="function",
                declaration_range=ByteRange(0, len(source)),
                signature_range=ByteRange(0, body_start - 1),
                body_range=ByteRange(body_start, len(source)),
            )
        ],
    )

    assert (
        JavaScriptLanguage.skeleton_builder(JavaScriptLanguage.spec).build(parsed)
        == "function run() { /* ... */ }"
    )


def test_skeleton_preserves_imports_classes_signatures_and_jsdoc() -> None:
    source = b"""import {service} from "./service.js";
/** Public service. */
export class Client extends Base {
    field = config;
    /** Fetch a record. */
    async fetch(id) { return service(id); }
    get value() { return this.field; }
    #private() { return secret(); }
}
export function* records(limit) { yield* service(limit); }
"""
    parsed = parse(source, JavaScriptLanguage)
    skeleton = JavaScriptLanguage.skeleton_builder(JavaScriptLanguage.spec).build(parsed)

    assert (
        skeleton
        == """import {service} from "./service.js";
/** Public service. */
export class Client extends Base {
    field = config;
    /** Fetch a record. */
    async fetch(id) { /* ... */ }
    get value() { /* ... */ }
    #private() { /* ... */ }
}
export function* records(limit) { /* ... */ }
"""
    )
    assert not get_parser("javascript").parse(skeleton.encode()).root_node.has_error


@pytest.mark.parametrize(
    "source",
    [
        b"const run = value => value + 1;",
        b"const run = async value => await service(value);",
        b"const run = () => ({value: input});",
        b"const run = () => <Widget value={input} />;",
        b"const run = function named(value) { return value; };",
        b"const run = function* (value) { yield value; };",
        b"const object = { run(value) { return value; } };",
        b"register(function (value) { return value; });",
        b"const view = <Widget render={() => <Child />} />;",
        b"export default function (value) { return value; }",
    ],
)
def test_skeleton_handles_function_forms_and_anonymous_callbacks(source: bytes) -> None:
    parser = get_parser("javascript")
    parsed = parse(source, JavaScriptLanguage)
    assert not parsed.has_errors

    skeleton = SkeletonBuilder(JavaScriptLanguage.spec).build(parsed)

    assert "{ /* ... */ }" in skeleton
    assert skeleton != source.decode()
    assert not parser.parse(skeleton.encode()).root_node.has_error


def test_skeleton_elides_outermost_bodies_without_overlapping_edits() -> None:
    source = b"""function outer(value) {
    function inner() { return value; }
    return () => inner();
}
function other() { return result; }
"""
    parsed = parse(source, JavaScriptLanguage)

    assert SkeletonBuilder(JavaScriptLanguage.spec).build(parsed) == (
        "function outer(value) { /* ... */ }\nfunction other() { /* ... */ }\n"
    )


def test_skeleton_handles_callbacks_in_default_parameters() -> None:
    source = b"function run(callback = () => defaultValue) { return callback(); }"
    parser = get_parser("javascript")
    parsed = parse(source, JavaScriptLanguage)

    skeleton = SkeletonBuilder(JavaScriptLanguage.spec).build(parsed)

    assert skeleton == "function run(callback = () => { /* ... */ }) { /* ... */ }"
    assert not parser.parse(skeleton.encode()).root_node.has_error


def test_skeleton_preserves_utf8_offsets_and_surrounding_source() -> None:
    source = 'const café = "é";\r\nfunction run(value) { return "你好"; }\r\n'.encode()
    parsed = parse(source, JavaScriptLanguage)

    assert SkeletonBuilder(JavaScriptLanguage.spec).build(parsed) == (
        'const café = "é";\r\nfunction run(value) { /* ... */ }\r\n'
    )


@pytest.mark.parametrize(
    "source",
    [
        b"",
        b"// comment\nconst value = input;\n",
        b"function empty() {}\nconst noop = () => {};\n",
        b"function broken(value) { return value;",
    ],
)
def test_skeleton_preserves_empty_unchanged_and_incomplete_source(source: bytes) -> None:
    parsed = parse(source, JavaScriptLanguage)

    assert SkeletonBuilder(JavaScriptLanguage.spec).build(parsed) == source.decode()
