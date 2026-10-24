from __future__ import annotations

import math
import re
from collections import Counter
from typing import ClassVar, NamedTuple

from contextcraft.models import SecretKind, SecretMatch


class SanitizationResult(NamedTuple):
    sanitized_content: str
    redacted_secrets: list[SecretMatch]


class _SecretPattern(NamedTuple):
    kind: SecretKind
    regex: re.Pattern[str]


class SecretSanitizer:
    _PEM_PRIVATE_KEY_RE: ClassVar[re.Pattern[str]] = re.compile(
        "-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\\s\\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----"
    )
    _TOKEN_PATTERNS: ClassVar[tuple[_SecretPattern, ...]] = (
        _SecretPattern(
            SecretKind.OPENAI_API_KEY,
            re.compile("\\bsk-(?!ant-)(?:proj-|svcacct-|None-)?[A-Za-z0-9_-]{20,}\\b"),
        ),
        _SecretPattern(
            SecretKind.ANTHROPIC_API_KEY,
            re.compile("\\bsk-ant-(?:api\\d+-|admin\\d+-)?[A-Za-z0-9_-]{20,}\\b"),
        ),
        _SecretPattern(
            SecretKind.AWS_ACCESS_KEY,
            re.compile("\\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\\b"),
        ),
        _SecretPattern(
            SecretKind.GITHUB_TOKEN,
            re.compile(
                "\\b(?:(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{22,255})\\b"
            ),
        ),
        _SecretPattern(SecretKind.GOOGLE_API_KEY, re.compile("\\bAIza[0-9A-Za-z_-]{35}\\b")),
        _SecretPattern(SecretKind.SLACK_TOKEN, re.compile("\\bxox[baprs]-[0-9A-Za-z-]{10,}\\b")),
        _SecretPattern(
            SecretKind.STRIPE_KEY, re.compile("\\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{20,}\\b")
        ),
        _SecretPattern(SecretKind.HUGGINGFACE_TOKEN, re.compile("\\bhf_[A-Za-z0-9]{34,}\\b")),
        _SecretPattern(SecretKind.NPM_TOKEN, re.compile("\\bnpm_[A-Za-z0-9]{36}\\b")),
        _SecretPattern(
            SecretKind.DATABRICKS_TOKEN, re.compile("\\bdapi[0-9a-f]{32}(?:-[0-9]+)?\\b")
        ),
        _SecretPattern(
            SecretKind.JWT,
            re.compile("\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}"),
        ),
        # Patterns with a `value` group redact only that group and keep the surrounding text.
        _SecretPattern(
            SecretKind.BEARER_TOKEN,
            re.compile("\\bBearer\\s+(?P<value>[A-Za-z0-9._~+/-]{16,}=*)", re.IGNORECASE),
        ),
        _SecretPattern(
            SecretKind.CONNECTION_STRING_PASSWORD,
            re.compile(
                "\\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\\s:/@\"'`]+:(?P<value>[^\\s@/\"'`]+)@[^\\s@/\"'`]"
            ),
        ),
    )
    _SECRET_KEY_WORDS: ClassVar[str] = (
        r"(?:[a-zA-Z0-9_]*?(?:api_?key|secret_?key|client_?secret|access_?token|auth_?token|"
        r"private_?key|password|passwd|pwd|jwt_?secret|secret)[a-zA-Z0-9_]*"
        # Bare token words must end the key so names like `max_tokens` stay untouched.
        r"|[a-zA-Z0-9_]*?(?:token|bearer|credentials?))"
    )
    _SECRET_ASSIGNMENT_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?P<prefix>(?P<key_quote>["']?)\b(?P<key>"""
        + _SECRET_KEY_WORDS
        + r""")(?P=key_quote)\s*[:=]\s*)(?P<quote>["'])(?P<value>[^"'\r\n]{1,4096})(?P=quote)""",
        re.IGNORECASE,
    )
    _UNQUOTED_ASSIGNMENT_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""^(?P<prefix>[ \t]*(?:-[ \t]+)?(?P<key>"""
        + _SECRET_KEY_WORDS
        + r""")[ \t]*[:=][ \t]*)(?P<value>[^\s"'#|>&*!{}\[\]][^\r\n]*?)(?=[ \t]+#|[ \t]*\r?$)""",
        re.IGNORECASE,
    )
    _UNQUOTED_CONFIG_SUFFIXES: ClassVar[tuple[str, ...]] = (
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
    )
    _PASSWORD_KEY_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:password|passwd|passphrase)$", re.IGNORECASE
    )
    _CREDENTIAL_FREE_URL_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s@]*"
    )
    # Variable references and templates: $VAR, ${VAR}, ${{ secrets.X }}, {{ x }}, {name}.
    _REFERENCE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})"
        r"|\$?\{\{.*\}\}|\{[A-Za-z0-9_.]*\}"
    )
    # Values naming another setting, e.g. `api_key_env = "OPENAI_API_KEY"`.
    _ENV_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")
    _DOTENV_LINE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""^(?P<export>export\s+)?(?P<key>[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|CREDENTIAL|DATABASE_URL|REDIS_URL)[A-Z0-9_]*)\s*=\s*(?P<quote>["']?)(?P<value>[^\r\n]*?)(?P=quote)(?=[ \t]*(?:#|\r?$))""",
        re.IGNORECASE,
    )
    _SAFE_VALUES: ClassVar[frozenset[str]] = frozenset(
        {
            "example",
            "changeme",
            "placeholder",
            "dummy",
            "todo",
            "none",
            "null",
            "true",
            "false",
            "your-api-key",
            "your-api-key-here",
            "your_api_key",
            "your_api_key_here",
            "password",
            "secret",
        }
    )

    @classmethod
    def sanitize(cls, content: str, file_path: str = "") -> tuple[str, int]:
        result = cls.sanitize_detailed(content, file_path=file_path)
        return (result.sanitized_content, len(result.redacted_secrets))

    @classmethod
    def sanitize_detailed(cls, content: str, file_path: str = "") -> SanitizationResult:
        if not content:
            return SanitizationResult(sanitized_content=content, redacted_secrets=[])
        matches: list[SecretMatch] = []
        working = content

        def replace_pem(match: re.Match[str]) -> str:
            raw_block = match.group(0)
            line_num = working[: match.start()].count("\n") + 1
            placeholder = f"<REDACTED_SECRET:{SecretKind.PRIVATE_KEY_BLOCK.value}>"
            matches.append(
                SecretMatch(
                    kind=SecretKind.PRIVATE_KEY_BLOCK,
                    line_number=line_num,
                    redacted_placeholder=placeholder,
                    masked_preview="-----BEGIN...PRIVATE KEY-----",
                )
            )
            return placeholder + "".join(re.findall(r"\r\n|\r|\n", raw_block))

        working = cls._PEM_PRIVATE_KEY_RE.sub(replace_pem, working)
        lines = working.splitlines(keepends=True)
        is_dotenv = cls._is_dotenv_file(file_path)
        is_unquoted_config = file_path.lower().endswith(cls._UNQUOTED_CONFIG_SUFFIXES)
        sanitized_lines: list[str] = []
        for idx, line in enumerate(lines, start=1):
            updated_line = line
            for pattern_spec in cls._TOKEN_PATTERNS:
                updated_line = cls._apply_token_pattern(
                    updated_line, line_number=idx, pattern_spec=pattern_spec, matches=matches
                )
            if is_dotenv:
                updated_line = cls._apply_dotenv_pattern(
                    updated_line, line_number=idx, matches=matches
                )
            updated_line = cls._apply_assignment_pattern(
                updated_line, line_number=idx, matches=matches
            )
            if is_unquoted_config:
                updated_line = cls._apply_unquoted_assignment_pattern(
                    updated_line, line_number=idx, matches=matches
                )
            sanitized_lines.append(updated_line)
        return SanitizationResult(
            sanitized_content="".join(sanitized_lines), redacted_secrets=matches
        )

    @classmethod
    def _apply_token_pattern(
        cls, line: str, line_number: int, pattern_spec: _SecretPattern, matches: list[SecretMatch]
    ) -> str:

        def replace_match(match: re.Match[str]) -> str:
            has_value = "value" in match.re.groupindex
            secret_val = match.group("value") if has_value else match.group(0)
            if has_value and not cls._is_inline_secret(secret_val):
                return match.group(0)
            placeholder = f"<REDACTED_SECRET:{pattern_spec.kind.value}>"
            matches.append(
                SecretMatch(
                    kind=pattern_spec.kind,
                    line_number=line_number,
                    redacted_placeholder=placeholder,
                    masked_preview=cls._mask_secret(secret_val),
                )
            )
            if not has_value:
                return placeholder
            start, end = match.span("value")
            offset = match.start()
            whole = match.group(0)
            return whole[: start - offset] + placeholder + whole[end - offset :]

        return pattern_spec.regex.sub(replace_match, line)

    @classmethod
    def _apply_assignment_pattern(
        cls, line: str, line_number: int, matches: list[SecretMatch]
    ) -> str:

        def replace_match(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            quote = match.group("quote")
            value = match.group("value")
            if not cls._should_redact(match.group("key"), value):
                return match.group(0)
            placeholder = f"<REDACTED_SECRET:{SecretKind.GENERIC_HIGH_ENTROPY.value}>"
            matches.append(
                SecretMatch(
                    kind=SecretKind.GENERIC_HIGH_ENTROPY,
                    line_number=line_number,
                    redacted_placeholder=placeholder,
                    masked_preview=cls._mask_secret(value),
                )
            )
            return f"{prefix}{quote}{placeholder}{quote}"

        return cls._SECRET_ASSIGNMENT_RE.sub(replace_match, line)

    @classmethod
    def _apply_unquoted_assignment_pattern(
        cls, line: str, line_number: int, matches: list[SecretMatch]
    ) -> str:
        """Scrub `key: value` lines in YAML/INI-style files where values need no quotes."""

        def replace_match(match: re.Match[str]) -> str:
            key = match.group("key")
            value = match.group("value")
            # URLs without userinfo (endpoints, issuers) are configuration, not credentials.
            if not cls._PASSWORD_KEY_RE.search(key) and cls._CREDENTIAL_FREE_URL_RE.fullmatch(
                value
            ):
                return match.group(0)
            if not cls._should_redact(key, value):
                return match.group(0)
            placeholder = f"<REDACTED_SECRET:{SecretKind.GENERIC_HIGH_ENTROPY.value}>"
            matches.append(
                SecretMatch(
                    kind=SecretKind.GENERIC_HIGH_ENTROPY,
                    line_number=line_number,
                    redacted_placeholder=placeholder,
                    masked_preview=cls._mask_secret(value),
                )
            )
            return f"{match.group('prefix')}{placeholder}"

        return cls._UNQUOTED_ASSIGNMENT_RE.sub(replace_match, line)

    @classmethod
    def _apply_dotenv_pattern(cls, line: str, line_number: int, matches: list[SecretMatch]) -> str:

        def replace_match(match: re.Match[str]) -> str:
            export_prefix = match.group("export") or ""
            key = match.group("key")
            quote = match.group("quote") or ""
            value = match.group("value").strip()
            if not cls._should_redact(key, value, check_entropy=False):
                return match.group(0)
            placeholder = f"<REDACTED_SECRET:{SecretKind.ENV_SECRET_ASSIGNMENT.value}>"
            matches.append(
                SecretMatch(
                    kind=SecretKind.ENV_SECRET_ASSIGNMENT,
                    line_number=line_number,
                    redacted_placeholder=placeholder,
                    masked_preview=cls._mask_secret(value),
                )
            )
            return f"{export_prefix}{key}={quote}{placeholder}{quote}"

        return cls._DOTENV_LINE_RE.sub(replace_match, line)

    @classmethod
    def _should_redact(cls, key: str, value: str, *, check_entropy: bool = True) -> bool:
        """Decide whether a value assigned to a secret-looking key is a real credential."""
        if cls._is_placeholder(value):
            return False
        # Passwords are often short and low-entropy, so only placeholders exempt them.
        if cls._PASSWORD_KEY_RE.search(key):
            return len(value.strip()) >= 4
        if cls._is_benign_value(value):
            return False
        return not (check_entropy and cls._shannon_entropy(value) < 3.3 and len(value) < 16)

    @classmethod
    def _is_inline_secret(cls, value: str) -> bool:
        """Filter credentials embedded in URLs or headers, where test fixtures abound."""
        if cls._is_placeholder(value) or len(value) < 6:
            return False
        return value.lower() not in {"pass", "passwd", "test", "user"} and (
            cls._shannon_entropy(value) >= 2.5
        )

    @classmethod
    def _is_benign_value(cls, value: str) -> bool:
        return len(value.strip()) < 8 or cls._is_placeholder(value)

    @classmethod
    def _is_placeholder(cls, value: str) -> bool:
        stripped = value.strip()
        lower = stripped.lower()
        if lower in cls._SAFE_VALUES:
            return True
        if any(lower == f"<redacted_secret:{kind.value.lower()}>" for kind in SecretKind):
            return True
        return bool(cls._REFERENCE_RE.fullmatch(stripped) or cls._ENV_NAME_RE.fullmatch(stripped))

    @staticmethod
    def _is_dotenv_file(file_path: str) -> bool:
        if not file_path:
            return False
        name = file_path.rsplit("/", maxsplit=1)[-1].lower()
        return name == ".env" or name.startswith(".env.")

    @staticmethod
    def _shannon_entropy(data: str) -> float:
        if not data:
            return 0.0
        length = len(data)
        counts = Counter(data)
        return -sum(count / length * math.log2(count / length) for count in counts.values())

    @staticmethod
    def _mask_secret(secret: str) -> str:
        clean = secret.strip()
        if len(clean) <= 8:
            return "***"
        return f"{clean[:4]}...{clean[-4:]}"
