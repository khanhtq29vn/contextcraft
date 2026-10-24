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


@pytest.mark.parametrize("file_path", ["config.py", "config.json", ".env.production"])
@pytest.mark.parametrize(
    "secret",
    [
        "pineapple violet meadow",
        "noneR7nY9u2K5v8X4q6Z",
        "test_R7nY9u2K5v8X4q6Z",
        "exampleR7nY9u2K5v8X4q6Z",
        "your-R7nY9u2K5v8X4q6Z",
        "fake_R7nY9u2K5v8X4q6Z",
        "mock-R7nY9u2K5v8X4q6Z",
        "$R7nY9u2K5v8X4q6Z!",
        "http://localhost.evil.invalid/R7nY9u2K5v8X4q6Z",
        "/R7nY9u2K5v8X4q6Z",
        "R7nY9u2K5v8X4q6Z<REDACTED_SECRET:GENERIC_SECRET>",
    ],
)
def test_sanitizer_does_not_exempt_passphrases_or_placeholder_prefixes(
    file_path: str, secret: str
) -> None:
    source = (
        json.dumps({"password": secret})
        if file_path.endswith(".json")
        else f"PASSWORD={json.dumps(secret)}\n"
    )

    result = SecretSanitizer.sanitize_detailed(source, file_path)

    assert secret not in result.sanitized_content
    assert len(result.redacted_secrets) == 1
    if file_path.endswith(".json"):
        assert json.loads(result.sanitized_content)["password"].startswith("<REDACTED_SECRET:")
    assert SecretSanitizer.sanitize_detailed(result.sanitized_content, file_path) == (
        result.sanitized_content,
        [],
    )


@pytest.mark.parametrize("file_path", ["config.py", ".env.production"])
@pytest.mark.parametrize(
    "value",
    [
        "changeme",
        "placeholder",
        "your-api-key-here",
        "your_api_key_here",
        "$PASSWORD",
        "${PASSWORD}",
        "<REDACTED_SECRET:GENERIC_SECRET>",
    ],
)
def test_sanitizer_preserves_exact_placeholders_and_variable_references(
    file_path: str, value: str
) -> None:
    source = f"PASSWORD={json.dumps(value)}\n"

    result = SecretSanitizer.sanitize_detailed(source, file_path)

    assert result.sanitized_content == source
    assert result.redacted_secrets == []


def test_sanitizer_is_idempotent_and_preserves_quoted_code() -> None:
    source = 'const key = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";\n'
    first = SecretSanitizer.sanitize_detailed(source, "key.js")
    second = SecretSanitizer.sanitize_detailed(first.sanitized_content, "key.js")

    assert first.sanitized_content == second.sanitized_content
    assert not second.redacted_secrets
    assert not get_parser("javascript").parse(first.sanitized_content.encode()).root_node.has_error


_LONG_SECRET = "Zm9vYmFyYmF6cXV4" * 12  # 192 characters, longer than any old length cap
_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


@pytest.mark.parametrize(
    ("file_path", "source", "secret", "kind"),
    [
        (
            "config.py",
            f'client_secret = "{_LONG_SECRET}"\n',
            _LONG_SECRET,
            SecretKind.GENERIC_HIGH_ENTROPY,
        ),
        ("config.py", f'TOKEN = "{_JWT}"\n', _JWT, SecretKind.JWT),
        ("app.js", f"fetch(url, {{ jwt: '{_JWT}' }});\n", _JWT, SecretKind.JWT),
        (
            "client.py",
            'headers = {"Authorization": "Bearer R7nY9u2K5v8X4q6ZR7nY9u2K"}\n',
            "R7nY9u2K5v8X4q6ZR7nY9u2K",
            SecretKind.BEARER_TOKEN,
        ),
        (
            "settings.py",
            'DB = "postgres://admin:Sup3rS3cret@db.internal:5432/app"\n',
            "Sup3rS3cret",
            SecretKind.CONNECTION_STRING_PASSWORD,
        ),
        (
            "hub.py",
            'HF = "hf_' + "a1B2" * 9 + '"\n',
            "hf_" + "a1B2" * 9,
            SecretKind.HUGGINGFACE_TOKEN,
        ),
        (
            ".npmrc",
            "//registry.npmjs.org/:_authToken=npm_" + "a1B2" * 9 + "\n",
            "npm_" + "a1B2" * 9,
            SecretKind.NPM_TOKEN,
        ),
        (
            "job.py",
            'host_token = "dapi' + "0123456789abcdef" * 2 + '"\n',
            "dapi" + "0123456789abcdef" * 2,
            SecretKind.DATABRICKS_TOKEN,
        ),
        ("settings.py", 'password = "hunter2"\n', "hunter2", SecretKind.GENERIC_HIGH_ENTROPY),
        (".env", "DB_PASSWORD=hunter2\n", "hunter2", SecretKind.ENV_SECRET_ASSIGNMENT),
        (
            "config.yaml",
            "database:\n  password: Sup3rS3cretPassw0rd # prod\n",
            "Sup3rS3cretPassw0rd",
            SecretKind.GENERIC_HIGH_ENTROPY,
        ),
        (
            "credentials.ini",
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n",
            "wJalrXUtnFEMI",
            SecretKind.GENERIC_HIGH_ENTROPY,
        ),
    ],
)
def test_sanitizer_redacts_previously_leaked_secret_shapes(
    file_path: str, source: str, secret: str, kind: SecretKind
) -> None:
    result = SecretSanitizer.sanitize_detailed(source, file_path)

    assert secret not in result.sanitized_content
    assert [match.kind for match in result.redacted_secrets] == [kind]
    assert result.sanitized_content.count("\n") == source.count("\n")
    assert SecretSanitizer.sanitize_detailed(result.sanitized_content, file_path) == (
        result.sanitized_content,
        [],
    )


@pytest.mark.parametrize(
    ("file_path", "source"),
    [
        ("config.yaml", "token_url: https://auth.example.com/oauth/token\n"),
        ("config.yaml", "password: ${DB_PASSWORD}\n"),
        ("config.yaml", "token: ${{ secrets.DEPLOY_TOKEN }}\n"),
        ("config.yaml", "secret_name: my-app-secret\n"),
        ("config.yaml", "credentials:\n  - name: deploy\n"),
        ("config.yaml", "token: |\n  multi-line\n"),
        ("config.py", 'max_tokens = "8000"\n'),
        ("config.py", 'tokenizer_encoding = "cl100k_base"\n'),
        ("config.py", 'password_hash_algorithm = "bcrypt"\n'),
        ("config.py", 'token_type = "Bearer"\n'),
        ("config.py", 'url = "postgres://user:password@localhost/db"\n'),
        ("config.py", 'url = "postgres://user:${DB_PASS}@localhost/db"\n'),
        ("config.py", 'url = "https://example.com/users/a@b"\n'),
    ],
)
def test_sanitizer_keeps_configuration_that_only_looks_secret(file_path: str, source: str) -> None:
    result = SecretSanitizer.sanitize_detailed(source, file_path)

    assert result.sanitized_content == source
    assert result.redacted_secrets == []


@pytest.mark.parametrize(
    ("file_path", "source"),
    [
        (".github/workflows/ci.yml", "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"),
        ("config.py", 'api_key_env = "OPENAI_API_KEY"\n'),
        ("models.py", '    GITHUB_TOKEN = "GITHUB_TOKEN"\n'),
        (
            "test_utils.py",
            '("http://user:pass@complex.url.com/path?query=yes", ("user", "pass")),\n',
        ),
        ("test_utils.py", '"http://user:pass%20pass@complex.url.com/path?query=yes",\n'),
        ("test_utils.py", 'f"http://{ENCODED_USER}:{ENCODED_PASSWORD}@request.com/url.html",\n'),
        ("test_utils.py", '("hTTp://u:p@Some.Host/path", "http://some.host.proxy"),\n'),
    ],
)
def test_sanitizer_ignores_references_and_url_fixtures(file_path: str, source: str) -> None:
    result = SecretSanitizer.sanitize_detailed(source, file_path)

    assert result.sanitized_content == source
    assert result.redacted_secrets == []
