from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.ast.parser import parse
from contextcraft.languages.base import LanguageSpec
from contextcraft.languages.builtin import default_registry
from contextcraft.languages.structural import StructuralSkeletonBuilder


def test_structural_skeleton_elides_outermost_ranges() -> None:
    source = b"a OUTER INNER BODY z"
    parsed = ParsedAst(
        source=source,
        symbols=[
            Symbol(
                name="outer",
                kind="function",
                declaration_range=ByteRange(0, len(source)),
                signature_range=ByteRange(0, 1),
                body_range=ByteRange(2, 18),
            ),
            Symbol(
                name="inner",
                kind="function",
                declaration_range=ByteRange(8, 18),
                signature_range=ByteRange(8, 13),
                body_range=ByteRange(14, 18),
            ),
        ],
    )
    language = default_registry().get("python")
    assert language is not None
    builder = language.skeleton_builder(language.spec)

    assert builder.build(parsed) == "a ... z"
    assert parsed.source == source


def test_structural_skeleton_without_elision_preserves_source() -> None:
    parsed = ParsedAst(source=b"original source\r\n")
    builder = StructuralSkeletonBuilder(LanguageSpec(id="test"))

    assert builder.build(parsed) == parsed.source.decode()


@pytest.mark.parametrize(
    "language_id,source",
    [
        ("ruby", 'def run(value)\r\n "你好" + value\r\nend\r\n'.encode()),
        ("lua", 'local run = function(value) return "你好" .. value end\r\n'.encode()),
        ("kotlin", 'fun run(value: String): String = "你好" + value\r\n'.encode()),
        ("scala", 'def run(value: String): String = "你好" + value\r\n'.encode()),
        ("r", 'run <- function(value) paste("你好", value)\r\n'.encode()),
    ],
)
def test_native_expression_bodies_preserve_utf8_offsets(language_id: str, source: bytes) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    parsed = parse(source, language)
    assert not parsed.has_errors
    skeleton = language.skeleton_builder(language.spec).build(parsed)
    assert "你好" not in skeleton
    assert skeleton.endswith("\r\n")
    assert not get_parser(language.spec.parser_id).parse(skeleton.encode()).root_node.has_error
    signatures = language.signatures_builder(language.spec).build(parsed)
    assert not get_parser(language.spec.parser_id).parse(signatures.encode()).root_node.has_error
