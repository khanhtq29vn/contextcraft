from __future__ import annotations

import pytest

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


@pytest.mark.parametrize(
    "language_id,source,kept,removed",
    [
        (
            "javascript",
            'import Base from "keep"; import {unused} from "drop"; export class Client extends Base { run() { return unused(); } }',
            'import Base from "keep";',
            'import {unused} from "drop";',
        ),
        (
            "typescript",
            'import type {Thing as Model} from "keep"; import {unused} from "drop"; export function run(value: Model): Model { return unused(value); }',
            'import type {Thing as Model} from "keep";',
            'import {unused} from "drop";',
        ),
        (
            "tsx",
            'import type {Thing as Model} from "keep"; import {unused} from "drop"; export function run(value: Model): Model { return unused(value); }',
            'import type {Thing as Model} from "keep";',
            'import {unused} from "drop";',
        ),
        (
            "rust",
            "use keep::{nested::Thing as Model, Other}; use drop::unused; pub fn run(value: Model) -> Model { unused(value) }",
            "use keep::{nested::Thing as Model, Other};",
            "use drop::unused;",
        ),
        (
            "go",
            'package demo\nimport "time"\nimport "fmt"\nfunc Run(value time.Time) time.Time { fmt.Println(value); return value }',
            'import "time"',
            'import "fmt"',
        ),
        (
            "java",
            "import keep.Model; import drop.Unused; class Client { public Model run(Model value) { Unused.call(); return value; } }",
            "import keep.Model;",
            "import drop.Unused;",
        ),
        (
            "csharp",
            "using Model = Keep.Type; using Unused = Drop.Type; public class Client { public Model Run(Model value) { Unused.Call(); return value; } }",
            "using Model = Keep.Type;",
            "using Unused = Drop.Type;",
        ),
        (
            "kotlin",
            "import keep.Thing as Model\nimport drop.Unused\nclass Client {\n fun run(value: Model): Model {\n Unused.call()\n return value\n }\n}\n",
            "import keep.Thing as Model",
            "import drop.Unused",
        ),
        (
            "scala",
            "import keep.{Thing => Model}\nimport drop.Unused\nclass Client { def run(value: Model): Model = { Unused.call(); value } }",
            "import keep.{Thing => Model}",
            "import drop.Unused",
        ),
        (
            "scala",
            "import keep.Thing as Model\nimport drop.Unused\nclass Client { def run(value: Model): Model = { Unused.call(); value } }",
            "import keep.Thing as Model",
            "import drop.Unused",
        ),
        (
            "swift",
            "import struct Foundation.Date\nimport struct Other.Unused\nfunc run(value: Date) -> Date { let ignored = Unused(); return value }",
            "import struct Foundation.Date",
            "import struct Other.Unused",
        ),
        (
            "php",
            "<?php\nuse Keep\\Model; use Drop\\Unused; class Client { public function run(model $value): model { Unused::call(); return $value; } }",
            "use Keep\\Model;",
            "use Drop\\Unused;",
        ),
    ],
)
def test_signature_builders_trim_only_implementation_imports(
    language_id: str, source: str, kept: str, removed: str
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source.encode(), language)
    assert not parsed.has_errors
    original_imports = list(parsed.imports)

    signatures = language.signatures_builder(language.spec).build(parsed)

    assert kept in signatures
    assert removed not in signatures
    assert parsed.imports == original_imports
    assert parsed.source == source.encode()


@pytest.mark.parametrize(
    "language_id,source",
    [
        (
            "javascript",
            'import "setup"; import {Model} from "models"; export {Model}; export function run() { return 1; }',
        ),
        (
            "typescript",
            'import type {Model} from "models"; export type {Model}; export function run(): void {}',
        ),
        ("rust", "pub use api::Model; use api::*; use api::Trait as _; pub fn run() {}"),
        (
            "go",
            'package demo\nimport "example.com/package"\nimport "math/rand/v2"\nimport _ "setup"\nimport . "namespace"\nfunc Run() {}',
        ),
        (
            "csharp",
            "using System; using static Other.Type; global using Alias = Other.Type; public class Client { public void Run() {} }",
        ),
        ("kotlin", "import keep.*\nfun run() {}"),
        ("scala", "import keep.*\nimport keep.given\ndef run(): Unit = {}"),
        ("swift", "import Foundation\n@_exported import Other\nfunc run() {}"),
        ("c", "#include <stdio.h>\nint run(void) { return 1; }"),
        ("cpp", "#include <vector>\nint run() { return 1; }"),
        ("ruby", 'require_relative "setup"\ndef run\n 1\nend\n'),
        ("lua", 'require("setup")\nfunction run() return 1 end\n'),
        ("r", "library(setup)\nrun <- function() { 1 }\n"),
        ("bash", "source ./setup.sh\nrun() { echo ready; }\n"),
        ("make", "include setup.mk\nbuild:\n\techo ready\n"),
        ("cmake", 'include(setup.cmake)\nfunction(run)\n message(STATUS "ready")\nendfunction()\n'),
        (
            "protobuf",
            'syntax = "proto3";\nimport public "setup.proto";\nmessage Model { string name = 1; }',
        ),
    ],
)
def test_effects_reexports_wildcards_and_unknown_bindings_are_preserved(
    language_id: str, source: str
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source.encode(), language)
    assert not parsed.has_errors
    assert parsed.imports

    assert (
        language.signatures_builder(language.spec).import_trimmer(language.spec).trim(parsed)
        == parsed.imports
    )


def test_partial_signatures_do_not_keep_imports_used_by_omitted_methods() -> None:
    language = default_registry().get("typescript")
    assert language is not None
    source = b'import {First} from "first"; import {Second} from "second"; export function first(value: First): First { return value; } export function second(value: Second): Second { return value; }'
    parsed = parse(source, language)
    first = next(symbol for symbol in parsed.symbols if symbol.name == "first")

    signatures = language.signatures_builder(language.spec).build_selected(parsed, [first])

    assert 'import {First} from "first";' in signatures
    assert 'import {Second} from "second";' not in signatures
    assert len(parsed.imports) == 2


def test_import_policies_are_explicit_and_cached_independently() -> None:
    from contextcraft.languages.imports import ImportTrimmer

    class DropImport(ImportTrimmer):
        @staticmethod
        def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
            return frozenset({"implementation_only"})

    class KeepImport(ImportTrimmer):
        @staticmethod
        def _bindings(parser_id: str | None, declaration: str) -> frozenset[str] | None:
            return frozenset({"run"})

    language = default_registry().get("python")
    assert language is not None
    parsed = parse(b"import dependency\ndef run():\n    return 1\n", language)

    assert ImportTrimmer(language.spec).trim(parsed) == parsed.imports
    assert DropImport(language.spec).trim(parsed) == []
    assert KeepImport(language.spec).trim(parsed) == parsed.imports
    assert DropImport(language.spec).trim(parsed) == []
