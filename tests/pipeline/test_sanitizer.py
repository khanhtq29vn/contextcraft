from __future__ import annotations

import json
import re

import pytest
from tree_sitter_language_pack import get_parser

from contextcraft.models import SecretKind
from contextcraft.sanitizer import SecretSanitizer


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
        "JWT_SECRET=super_secret_production_token_99887766\nPUBLIC_URL=http://localhost:3000\n"
    )
    clean, count = SecretSanitizer.sanitize(dotenv_text, file_path=".env.production")
    assert count == 1
    assert "<REDACTED_SECRET:ENV_SECRET>" in clean
    assert "http://localhost:3000" in clean


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("payload", ["", "MIIEowIBAAKCAQEA0123456789"])
def test_pem_redaction_preserves_every_line_ending(newline: str, payload: str) -> None:
    lines = ["-----BEGIN RSA PRIVATE KEY-----"]
    if payload:
        lines.append(payload)
    lines.append("-----END RSA PRIVATE KEY-----")
    source = "const key = `" + newline.join(lines) + "`;" + newline

    result = SecretSanitizer.sanitize_detailed(source, "key.js")

    assert re.findall(r"\r\n|\n", result.sanitized_content) == re.findall(r"\r\n|\n", source)
    assert "PRIVATE KEY-----" not in result.sanitized_content
    assert len(result.redacted_secrets) == 1
    assert result.redacted_secrets[0].kind == SecretKind.PRIVATE_KEY_BLOCK
    assert not get_parser("javascript").parse(result.sanitized_content.encode()).root_node.has_error


def test_anthropic_tokens_are_classified_without_double_counting() -> None:
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
    result = SecretSanitizer.sanitize_detailed(f'const key = "{secret}";', "key.js")

    assert secret not in result.sanitized_content
    assert [match.kind for match in result.redacted_secrets] == [SecretKind.ANTHROPIC_API_KEY]


def test_quoted_json_credentials_are_scrubbed_before_parsing() -> None:
    secret = "v9#mK8$pL2@qR5!zX7&wN4*bJ9"
    source = json.dumps({"password": secret, "nested": {"api_key": secret}, "safe": "your-api-key"})

    result = SecretSanitizer.sanitize_detailed(source, "config.json")
    payload = json.loads(result.sanitized_content)

    assert secret not in result.sanitized_content
    assert payload["password"].startswith("<REDACTED_SECRET:")
    assert payload["safe"] == "your-api-key"
    assert len(result.redacted_secrets) == 2


def test_dotenv_quoted_hashes_and_trailing_comments() -> None:
    source = 'TOKEN="abcdefgh#12345678" # keep this comment\r\nPASSWORD=longpassword123 # keep this too\r\n'

    result = SecretSanitizer.sanitize_detailed(source, ".env.production")

    assert "abcdefgh" not in result.sanitized_content
    assert "longpassword" not in result.sanitized_content
    assert "# keep this comment\r\n" in result.sanitized_content
    assert "# keep this too\r\n" in result.sanitized_content
    assert len(result.redacted_secrets) == 2


def test_sanitizer_is_idempotent_and_preserves_quoted_code() -> None:
    source = 'const key = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";\n'
    first = SecretSanitizer.sanitize_detailed(source, "key.js")
    second = SecretSanitizer.sanitize_detailed(first.sanitized_content, "key.js")

    assert first.sanitized_content == second.sanitized_content
    assert not second.redacted_secrets
    assert not get_parser("javascript").parse(first.sanitized_content.encode()).root_node.has_error
