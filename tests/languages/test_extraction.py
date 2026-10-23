from __future__ import annotations

import json

import pytest
from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.elider import Elider, FidelityLevel
from contextcraft.languages.builtin import default_registry

PROGRAMMING_LANGUAGES = {
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
    "lua",
    "r",
    "bash",
    "elixir",
    "zig",
}


@pytest.mark.parametrize(
    "language_id,source,expected",
    [
        (
            "python",
            b'def run(value):\n    """Run documentation."""\n    return transform(value)\n',
            "run",
        ),
        (
            "typescript",
            b"export function run(value: number): number { return transform(value); }",
            "run",
        ),
        ("tsx", b"export function View() { return <Widget value={input} />; }", "View"),
        ("rust", b"pub fn run(value: i32) -> i32 { transform(value) }", "run"),
        ("go", b"package main\nfunc Run(value int) int { return transform(value) }", "Run"),
        (
            "java",
            b"class Service { public int run(int value) { return transform(value); } }",
            "run",
        ),
        ("c", b"int run(int value) { return transform(value); }", "run"),
        (
            "cpp",
            b"class Service { public: int run(int value) { return transform(value); } };",
            "run",
        ),
        (
            "csharp",
            b"class Service { public int Run(int value) { return Transform(value); } }",
            "Run",
        ),
        (
            "json",
            b'{"long": "abcdefghijklmnopqrstuvwxyz123456789", "nested": {"flag": true}}',
            "long",
        ),
        ("yaml", b"long: abcdefghijklmnopqrstuvwxyz123456789\nnested:\n  flag: true\n", "long"),
        ("toml", b'[service]\nlong = "abcdefghijklmnopqrstuvwxyz123456789"\n', "long"),
        ("html", b"<main><h1>Title</h1><p>abcdefghijklmnopqrstuvwxyz123456789</p></main>", "main"),
        ("css", b".service { color: red; background: blue; margin: 10px; }", ".service"),
        ("scss", b".service { color: red; background: blue; margin: 10px; }", ".service"),
    ],
)
def test_structural_extraction_and_skeleton_syntax(
    language_id: str, source: bytes, expected: str
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    assert language.spec.parser_id is not None
    parsed = parse(source, language)

    assert not parsed.has_errors
    assert expected in parsed.defined_identifiers
    skeleton = language.skeleton_builder(language.spec).build(parsed)
    assert skeleton != source.decode()
    assert not get_parser(language.spec.parser_id).parse(skeleton.encode()).root_node.has_error
    for symbol in parsed.symbols:
        assert (
            0
            <= symbol.declaration_range.start_byte
            <= symbol.declaration_range.end_byte
            <= len(source)
        )
        if symbol.body_range is not None:
            assert symbol.body_range.start_byte <= symbol.body_range.end_byte <= len(source)
    tiers = Elider().render(parsed, language)
    assert [tiers[level].tokens for level in FidelityLevel] == sorted(
        tier.tokens for tier in tiers.values()
    )


@pytest.mark.parametrize(
    "language_id,source,qualified",
    [
        (
            "rust",
            b"pub struct Service {} impl Service { pub fn run(&self) { work(); } }",
            "Service.run",
        ),
        (
            "go",
            b"package main\ntype Service struct {}\nfunc (s Service) Run() { work(); }",
            "Service.Run",
        ),
    ],
)
def test_receiver_methods_link_to_their_type(
    language_id: str, source: bytes, qualified: str
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}

    assert symbols[qualified].kind == "method"
    assert symbols[qualified].parent is symbols["Service"]


def test_language_extraction_and_builders(
    language_case: tuple[str, str, bytes, str, list[str]],
) -> None:
    language_id, path, source, qualified, modules = language_case
    registry = default_registry()
    language = registry.get(language_id)
    assert language is not None
    assert registry.detect_candidates(path) == [language]
    parsed = parse(source, language)

    assert not parsed.has_errors
    assert qualified in {symbol.qualified_name for symbol in parsed.symbols}
    assert [item.module for item in parsed.imports] == modules
    for symbol in parsed.symbols:
        assert 0 <= symbol.declaration_range.start_byte <= symbol.signature_range.start_byte
        assert symbol.signature_range.end_byte <= symbol.declaration_range.end_byte <= len(source)
        if symbol.body_range is not None:
            assert symbol.declaration_range.start_byte <= symbol.body_range.start_byte
            assert symbol.body_range.end_byte <= symbol.declaration_range.end_byte

    skeleton = language.skeleton_builder(language.spec).build(parsed)
    signatures = language.signatures_builder(language.spec).build(parsed)
    parser = get_parser(language.spec.parser_id)
    assert not parser.parse(skeleton.encode()).root_node.has_error
    if language_id in PROGRAMMING_LANGUAGES:
        assert skeleton != source.decode()
        assert not parser.parse(signatures.encode()).root_node.has_error
        assert "service(value)" not in skeleton
    else:
        outline = json.loads(signatures)
        assert qualified in {item["name"] for item in outline}

    tiers = Elider().render(parsed, language)
    assert tiers[FidelityLevel.FULL].content == source.decode()
    assert [tiers[level].tokens for level in FidelityLevel] == sorted(
        tiers[level].tokens for level in FidelityLevel
    )
    assert parsed.source == source


@pytest.mark.parametrize(
    "language_id,source",
    [
        ("ruby", b'require(name)\nservice("not_a_module")\nrequire "#{name}"\n'),
        ("lua", b'local service = require(name)\nservice("not_a_module")\n'),
        ("r", b'library(paste("not", "static"))\nservice("not_a_module")\n'),
        ("bash", b'source "$name"\nservice "not_a_module"\n'),
    ],
)
def test_import_extraction_ignores_dynamic_paths_and_unrelated_calls(
    language_id: str, source: bytes
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert not parsed.has_errors
    assert parsed.imports == []


@pytest.mark.parametrize(
    "language_id,source,modules",
    [
        (
            "php",
            b'<?php\nuse App\\{Service, Client as User};\nrequire_once "service.php";\n',
            ["App\\Service", "App\\Client", "service.php"],
        ),
        ("make", b"include common.mk\n-include local.mk\n", ["common.mk", "local.mk"]),
        (
            "cmake",
            b"include(common.cmake)\nadd_subdirectory(src)\nfind_package(Pkg REQUIRED)\n",
            ["common.cmake", "src", "Pkg"],
        ),
    ],
)
def test_native_import_declarations(language_id: str, source: bytes, modules: list[str]) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert not parsed.has_errors
    assert [item.module for item in parsed.imports] == modules
