from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import HTMLLanguage


def skeleton(source: bytes) -> str:
    parsed = parse(source, HTMLLanguage)
    assert not parsed.has_errors
    return HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed)


def test_html_builders_preserve_structure_and_embedded_code() -> None:
    source = (
        b"<main><h1>Title</h1><p>Long paragraph content</p>"
        b"<script>run();</script><style>p { color: red; }</style></main>"
    )
    parsed = parse(source, HTMLLanguage)
    skeleton = HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed)
    signatures = HTMLLanguage.signatures_builder(HTMLLanguage.spec).build(parsed)

    assert not parsed.has_errors
    assert skeleton == (
        "<main><h1>Title</h1><p><!-- ... --></p>"
        "<script>run();</script><style>p { /* ... */ }</style></main>"
    )
    assert json.loads(signatures) == [
        {"name": "main", "kind": "element"},
        {"name": "main.h1", "kind": "heading"},
        {"name": "main.p", "kind": "element"},
        {"name": "main.script", "kind": "script"},
        {"name": "main.style", "kind": "style"},
    ]


def test_html_combines_text_and_embedded_edits_without_shifting_offsets() -> None:
    source = (
        "<main>\r\n<h1>你好</h1><p>Before café</p>\r\n"
        '<script type="module">\r\nimport { service } from "./service.js";\r\n'
        '/** Run documentation. */\r\nfunction run(value) { return service("你好", value); }\r\n'
        "</script><p>Between</p>\r\n"
        '<style media="screen">\r\n.card { color: red; margin: 10px; }\r\n</style>\r\n'
        "<p>After</p></main>"
    ).encode()
    parsed = parse(source, HTMLLanguage)
    assert not parsed.has_errors
    assert [region.language.spec.id for region in parsed.embedded_regions] == ["javascript", "css"]
    for region in parsed.embedded_regions:
        assert parsed.text(region.source_range) == region.parsed.source.decode()
        for symbol in region.parsed.symbols:
            start = region.source_range.start_byte + symbol.declaration_range.start_byte
            end = region.source_range.start_byte + symbol.declaration_range.end_byte
            assert source[start:end].decode() == region.parsed.text(symbol.declaration_range)

    builder = HTMLLanguage.skeleton_builder(HTMLLanguage.spec)
    with patch(
        "contextcraft.ast.parser.get_parser", side_effect=AssertionError("must not reparse")
    ):
        result = builder.build(parsed)
        assert builder.build(parsed) == result
    assert result == (
        "<main>\r\n<h1>你好</h1><p><!-- ... --></p>\r\n"
        '<script type="module">\r\nimport { service } from "./service.js";\r\n'
        "/** Run documentation. */\r\nfunction run(value) { /* ... */ }\r\n"
        "</script><p><!-- ... --></p>\r\n"
        '<style media="screen">\r\n.card { /* ... */ }\r\n</style>\r\n'
        "<p><!-- ... --></p></main>"
    )
    assert not get_parser("html").parse(result.encode()).root_node.has_error
    assert parsed.source == source


@pytest.mark.parametrize(
    "attributes",
    [
        "",
        'type="module"',
        'type="text/javascript"',
        "type=application/javascript",
        'TYPE=" TEXT/JAVASCRIPT; charset=UTF-8 "',
        'type="text&#47;javascript"',
        'type="application/ecmascript"',
        'type="" lang="js"',
        'language="JavaScript"',
    ],
)
def test_html_recognizes_inline_javascript_types(attributes: str) -> None:
    source = f"<SCRIPT {attributes}>function run() {{ return value; }}</SCRIPT>".encode()
    assert skeleton(source) == f"<SCRIPT {attributes}>function run() {{ /* ... */ }}</SCRIPT>"


@pytest.mark.parametrize("attributes", ["", 'type="text/css"', "TYPE=text/css", 'lang="css"'])
def test_html_recognizes_inline_styles(attributes: str) -> None:
    source = f"<style {attributes}>.card {{ color: red; }}</style>".encode()
    assert skeleton(source) == f"<style {attributes}>.card {{ /* ... */ }}</style>"


@pytest.mark.parametrize(
    "tag,attributes,content",
    [
        ("script", 'type="application/ld+json"', '{"name": "Keep me"}'),
        ("script", 'type="application/json"', '{"name": "Keep me"}'),
        ("script", 'type="importmap"', '{"imports": {"lib": "./lib.js"}}'),
        ("script", 'type="text/template"', "function run() { return value; }"),
        ("script", 'type="text/typescript"', "function run(value: number) { return value; }"),
        ("script", 'lang="ts"', "function run() { return value; }"),
        ("script", 'language="VBScript"', "function run() { return value; }"),
        ("script", 'src="./app.js"', "function ignored() { return value; }"),
        ("style", 'type="text/less"', ".card { color: red; }"),
        ("style", 'lang="scss"', ".card { color: red; }"),
        ("script", "", ""),
        ("style", "", ""),
    ],
)
def test_html_preserves_unsupported_external_and_empty_regions(
    tag: str, attributes: str, content: str
) -> None:
    source = f"<{tag} {attributes}>{content}</{tag}>".encode()
    parsed = parse(source, HTMLLanguage)
    assert not parsed.has_errors
    assert parsed.embedded_regions == []
    assert HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed) == source.decode()


def test_invalid_embedded_code_does_not_block_valid_regions() -> None:
    source = (
        b"<p>Text</p><script>function broken( {</script>"
        b"<style>.broken { color: </style>"
        b"<script>function run() { return value; }</script>"
        b"<style>.valid { color: red; }</style>"
    )
    parsed = parse(source, HTMLLanguage)
    assert not parsed.has_errors
    assert [region.parsed.has_errors for region in parsed.embedded_regions] == [
        True,
        True,
        False,
        False,
    ]
    assert HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed) == (
        "<p><!-- ... --></p><script>function broken( {</script>"
        "<style>.broken { color: </style>"
        "<script>function run() { /* ... */ }</script>"
        "<style>.valid { /* ... */ }</style>"
    )


@pytest.mark.parametrize("missing", ["javascript", "css"])
def test_missing_embedded_grammar_preserves_only_that_region(missing: str) -> None:
    source = (
        b"<script>function run() { return value; }</script><style>.card { color: red; }</style>"
    )

    def load(language_id: str) -> Parser:
        if language_id == missing:
            raise RuntimeError("grammar unavailable")
        return get_parser(language_id)

    with patch("contextcraft.ast.parser.get_parser", side_effect=load):
        parsed = parse(source, HTMLLanguage)
    assert not parsed.has_errors
    assert len(parsed.embedded_regions) == 2
    assert [
        region.language.spec.id for region in parsed.embedded_regions if region.parsed.has_errors
    ] == [missing]
    result = HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed)
    assert ("return value;" in result) == (missing == "javascript")
    assert ("color: red;" in result) == (missing == "css")


def test_html_keeps_embedded_custom_properties_and_nested_functions_safe() -> None:
    source = (
        b"<script>function outer() { function inner() { return value; } return inner(); }"
        b"function other() { return value; }</script>"
        b"<style>:root { --color: red; } @media screen { .card { color: var(--color); } }</style>"
    )
    result = skeleton(source)
    assert result == (
        "<script>function outer() { /* ... */ }function other() { /* ... */ }</script>"
        "<style>:root { --color: red; } @media screen { .card { /* ... */ } }</style>"
    )


def test_invalid_html_preserves_the_entire_source() -> None:
    source = b"<script>function run() { return value; }</script><div><"
    parsed = parse(source, HTMLLanguage)
    assert parsed.has_errors
    assert parsed.embedded_regions == []
    assert HTMLLanguage.skeleton_builder(HTMLLanguage.spec).build(parsed) == source.decode()
