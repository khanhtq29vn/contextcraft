"""Unit tests for `UniversalASTParser` and `MultiResolutionElider`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from contextcraft.ast_parser import UniversalASTParser
from contextcraft.elider import MultiResolutionElider, TokenCounter
from contextcraft.models import FidelityLevel, FileAnalysis


def test_ast_parser_extracts_python_symbols_and_preserves_docstrings(sample_repo: Path) -> None:
    """Verify Python classes, methods, docstrings, and post-docstring `body_range` spans."""
    jwt_code = (sample_repo / "src" / "auth" / "jwt_service.py").read_text(encoding="utf-8")
    parsed = UniversalASTParser.parse_detailed(jwt_code, "python")

    qual_names = {s.qualified_name or s.name for s in parsed.symbols}
    assert "JWTAuthService" in qual_names
    assert "JWTAuthService.verify_token" in qual_names
    assert "JWTAuthService.revoke_token" in qual_names

    verify_sym = next(s for s in parsed.symbols if s.name == "verify_token")
    assert verify_sym.kind == "method"
    assert verify_sym.docstring is not None
    assert "Verify JWT signature" in verify_sym.docstring
    assert verify_sym.body_range is not None

    # Ensure the elidable body_range starts strictly AFTER the docstring
    prefix_before_body = jwt_code.encode("utf-8")[: verify_sym.body_range.start_byte].decode(
        "utf-8"
    )
    assert "Verify JWT signature" in prefix_before_body


def test_ast_parser_extracts_typescript_symbols_and_fallback(sample_repo: Path) -> None:
    """Verify TypeScript extraction and source preservation without a parser."""
    ts_code = (sample_repo / "src" / "frontend" / "client.ts").read_text(encoding="utf-8")
    parsed = UniversalASTParser.parse_detailed(ts_code, "typescript")
    names = {s.name for s in parsed.symbols}
    assert "AuthResponse" in names
    assert "AuthApiClient" in names

    py_code = (sample_repo / "src" / "auth" / "jwt_service.py").read_text(encoding="utf-8")
    for language, code in (("python", py_code), ("typescript", ts_code)):
        with patch("contextcraft.ast_parser.HAS_TREE_SITTER", False):
            fallback = UniversalASTParser.parse_detailed(code, language)
        assert not fallback.symbols
        assert not fallback.imports
        assert not fallback.defined_identifiers
        assert not fallback.referenced_identifiers

        analysis = FileAnalysis(
            rel_path="sample",
            abs_path=str(sample_repo / "sample"),
            language=language,
            size_bytes=len(code.encode("utf-8")),
            raw_content=code,
            sanitized_content=code,
        )
        MultiResolutionElider(TokenCounter()).populate_tiers(analysis)
        for level in FidelityLevel:
            if level != FidelityLevel.TREE_ONLY:
                assert analysis.rendered_tiers[level] == code.strip() + "\n"


def test_multi_resolution_elider_monotonic_tiers_and_docstring_retention(
    sample_repo: Path,
) -> None:
    """Verify `MultiResolutionElider` produces monotonically smaller token tiers."""
    jwt_path = sample_repo / "src" / "auth" / "jwt_service.py"
    raw_code = jwt_path.read_text(encoding="utf-8")
    parsed = UniversalASTParser.parse_detailed(raw_code, "python")

    analysis = FileAnalysis(
        rel_path="src/auth/jwt_service.py",
        abs_path=str(jwt_path),
        language="python",
        size_bytes=len(raw_code.encode("utf-8")),
        raw_content=raw_code,
        sanitized_content=raw_code,
        symbols=parsed.symbols,
        defined_identifiers=parsed.defined_identifiers,
        referenced_identifiers=parsed.referenced_identifiers,
        imports=parsed.imports,
    )

    elider = MultiResolutionElider(TokenCounter())
    elider.populate_tiers(analysis)

    t_tree = analysis.tier_tokens[FidelityLevel.TREE_ONLY]
    t_sigs = analysis.tier_tokens[FidelityLevel.SIGNATURES_ONLY]
    t_skel = analysis.tier_tokens[FidelityLevel.SKELETON_WITH_DOCSTRINGS]
    t_full = analysis.tier_tokens[FidelityLevel.FULL_SOURCE]

    assert t_tree == 0
    assert 0 < t_sigs <= t_skel < t_full

    skel_text = analysis.rendered_tiers[FidelityLevel.SKELETON_WITH_DOCSTRINGS]
    # Signatures and docstrings must be preserved in SKEL tier
    assert (
        "def verify_token(self, token: str, current_timestamp: int) -> TokenPayload:" in skel_text
    )
    assert "Verify JWT signature and expiration timestamp" in skel_text
    # Implementation details must be elided
    assert "[elided" in skel_text
    assert "hmac.compare_digest" not in skel_text
