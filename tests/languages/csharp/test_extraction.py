from __future__ import annotations

from unittest.mock import patch

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.csharp.language import CSharpLanguage


def test_csharp_requests_the_canonical_download_name() -> None:
    source = b"class Service { public int Run(int value) { return Transform(value); } }"

    def load_parser(name: str) -> Parser:
        if name != "csharp":
            raise ValueError(f"Language {name!r} is not in the download manifest")
        return get_parser(name)

    with patch("contextcraft.ast.parser.get_parser", side_effect=load_parser) as loader:
        parsed = parse(source, CSharpLanguage)

    loader.assert_called_once_with("csharp")
    assert not parsed.has_errors
    assert {symbol.qualified_name for symbol in parsed.symbols} == {"Service", "Service.Run"}
