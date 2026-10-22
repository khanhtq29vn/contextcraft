from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from contextcraft.ast.parser import parse
from contextcraft.elider import Elider, FidelityLevel, TokenCounter
from contextcraft.languages.builtin import (
    PythonLanguage,
    TypeScriptLanguage,
)


def test_ast_parser_extracts_python_symbols_and_preserves_docstrings(sample_repo: Path) -> None:
    """Verify Python classes, methods, docstrings, and post-docstring body spans."""
    jwt_code = (sample_repo / "src" / "auth" / "jwt_service.py").read_bytes()
    parsed = parse(jwt_code, PythonLanguage)

    qual_names = {symbol.qualified_name for symbol in parsed.symbols}
    assert "JWTAuthService" in qual_names
    assert "JWTAuthService.verify_token" in qual_names
    assert "JWTAuthService.revoke_token" in qual_names

    verify_symbol = next(symbol for symbol in parsed.symbols if symbol.name == "verify_token")
    assert verify_symbol.kind == "method"
    assert verify_symbol.docstring_range is not None
    assert "Verify JWT signature" in parsed.text(verify_symbol.docstring_range)
    assert verify_symbol.body_range is not None
    assert verify_symbol.docstring_range.end_byte <= verify_symbol.body_range.start_byte
    assert "Verify JWT signature" in jwt_code[: verify_symbol.body_range.start_byte].decode()


def test_ast_parser_extracts_typescript_symbols_and_fallback(sample_repo: Path) -> None:
    """Verify TypeScript extraction and exact source preservation without a parser."""
    ts_code = (sample_repo / "src" / "frontend" / "client.ts").read_bytes()
    parsed = parse(ts_code, TypeScriptLanguage)
    names = {symbol.name for symbol in parsed.symbols}
    assert "AuthResponse" in names
    assert "AuthApiClient" in names

    py_code = (sample_repo / "src" / "auth" / "jwt_service.py").read_bytes()
    for language, source in ((PythonLanguage, py_code), (TypeScriptLanguage, ts_code)):
        with patch("contextcraft.ast.parser.get_parser", side_effect=RuntimeError("unavailable")):
            fallback = parse(source, language)
        assert fallback.has_errors
        assert not fallback.symbols
        assert not fallback.imports
        assert not fallback.defined_identifiers
        assert not fallback.referenced_identifiers

        tiers = Elider(TokenCounter()).render(fallback, language)
        for level in FidelityLevel:
            if level != FidelityLevel.TREE:
                assert tiers[level].content == source.decode()


def test_missing_grammar_preserves_source() -> None:
    source = b"def run():\n    return important_implementation()\n"
    with patch(
        "contextcraft.ast.parser.get_parser", side_effect=RuntimeError("grammar unavailable")
    ):
        parsed = parse(source, PythonLanguage)
    tiers = Elider().render(parsed, PythonLanguage)

    assert parsed.has_errors
    assert all(
        tiers[level].content == source.decode()
        for level in FidelityLevel
        if level != FidelityLevel.TREE
    )
