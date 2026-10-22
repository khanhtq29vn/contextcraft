"""Unit tests for `RepositoryScanner` and `SecretSanitizer`."""

from __future__ import annotations

from pathlib import Path

import pytest

from contextcraft.models import CompilationConfig, RepositoryNotFoundError, SecretKind
from contextcraft.sanitizer import SecretSanitizer
from contextcraft.scanner import RepositoryScanner


def test_scanner_respects_gitignore_and_skips_binaries(sample_repo: Path) -> None:
    """Verify `.gitignore` rules and binary files are excluded while valid code is scanned."""
    scanner = RepositoryScanner()
    outcome = scanner.scan(sample_repo)

    rel_paths = {f.rel_path for f in outcome.files}

    assert "src/auth/models.py" in rel_paths
    assert "src/auth/jwt_service.py" in rel_paths
    assert "src/api/routes.py" in rel_paths
    assert "src/frontend/client.ts" in rel_paths
    assert "src/utils/helpers.py" in rel_paths

    # Verify gitignored paths and binary assets were excluded
    assert "ignored_dir/skip_me.py" not in rel_paths
    assert "debug.log" not in rel_paths
    assert "assets/logo.dat" not in rel_paths
    assert outcome.binary_files_skipped >= 1
    assert outcome.ignored_files_skipped >= 2


def test_scanner_include_and_exclude_patterns(sample_repo: Path) -> None:
    """Verify user `include_patterns` and `exclude_patterns` filter files accurately."""
    cfg = CompilationConfig(
        include_patterns=["src/**/*.py"],
        exclude_patterns=["**/helpers.py"],
    )
    outcome = RepositoryScanner(cfg).scan(sample_repo)
    rel_paths = {f.rel_path for f in outcome.files}

    assert "src/auth/models.py" in rel_paths
    assert "src/auth/jwt_service.py" in rel_paths
    assert "src/frontend/client.ts" not in rel_paths
    assert "src/utils/helpers.py" not in rel_paths


def test_scanner_raises_on_missing_or_file_path(tmp_path: Path) -> None:
    """Verify `RepositoryNotFoundError` is raised for non-existent or non-directory paths."""
    scanner = RepositoryScanner()
    with pytest.raises(RepositoryNotFoundError):
        scanner.scan(tmp_path / "does_not_exist")

    file_target = tmp_path / "single_file.txt"
    file_target.write_text("hello", encoding="utf-8")
    with pytest.raises(RepositoryNotFoundError):
        scanner.scan(file_target)


def test_sanitizer_redacts_multiple_secret_types_preserving_syntax() -> None:
    """Verify API keys, PEM blocks, and high-entropy secrets are scrubbed safely."""
    raw_source = (
        'OPENAI_KEY = "sk-proj-1234567890abcdefghijklmnopQRSTUV"\n'
        'GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"\n'
        'AWS_ID = "AKIAIOSFODNN7EXAMPLE"\n'
        'db_password = "v9#mK8$pL2@qR5!zX7&wN4*bJ9"\n'
        'SAFE_PLACEHOLDER = "your-api-key-here"\n'
        "PEM = '''-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0123456789\n"
        "-----END RSA PRIVATE KEY-----'''\n"
    )

    res = SecretSanitizer.sanitize_detailed(raw_source, file_path="config.py")
    clean = res.sanitized_content
    kinds = {m.kind for m in res.redacted_secrets}

    assert SecretKind.OPENAI_API_KEY in kinds
    assert SecretKind.GITHUB_TOKEN in kinds
    assert SecretKind.AWS_ACCESS_KEY in kinds
    assert SecretKind.GENERIC_HIGH_ENTROPY in kinds
    assert SecretKind.PRIVATE_KEY_BLOCK in kinds

    assert "sk-proj-" not in clean
    assert "ghp_ABCDEF" not in clean
    assert "AKIAIOSFODNN7EXAMPLE" not in clean
    assert "v9#mK8$pL2" not in clean

    # Benign placeholder must remain untouched
    assert 'SAFE_PLACEHOLDER = "your-api-key-here"' in clean
    # Exact line count must be preserved so AST line offsets never shift
    assert len(clean.splitlines()) == len(raw_source.splitlines())


def test_sanitizer_dotenv_file_handling() -> None:
    """Verify `.env` secret assignments are scrubbed while benign URLs remain."""
    dotenv_text = (
        "JWT_SECRET=super_secret_production_token_99887766\n"
        "PUBLIC_URL=http://localhost:3000\n"
    )
    clean, count = SecretSanitizer.sanitize(dotenv_text, file_path=".env.production")
    assert count == 1
    assert "<REDACTED_SECRET:ENV_SECRET>" in clean
    assert "http://localhost:3000" in clean
