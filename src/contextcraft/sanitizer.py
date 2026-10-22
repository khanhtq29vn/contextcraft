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
    )
    _SECRET_ASSIGNMENT_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?P<prefix>(?P<key_quote>["']?)\b(?:[a-zA-Z0-9_]*?(?:api_?key|secret_?key|client_?secret|access_?token|auth_?token|private_?key|password|passwd|pwd|jwt_?secret|secret))[a-zA-Z0-9_]*(?P=key_quote)\s*[:=]\s*)(?P<quote>["'])(?P<value>[^"'\r\n]{8,128})(?P=quote)""",
        re.IGNORECASE,
    )
    _DOTENV_LINE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""^(?P<export>export\s+)?(?P<key>[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|CREDENTIAL|DATABASE_URL|REDIS_URL)[A-Z0-9_]*)\s*=\s*(?P<quote>["']?)(?P<value>[^\r\n]*?)(?P=quote)(?=[ \t]*(?:#|\r?$))""",
        re.IGNORECASE,
    )
    _SAFE_VALUE_PREFIXES: ClassVar[tuple[str, ...]] = (
        "<REDACTED_SECRET:",
        "your-",
        "your_",
        "example",
        "changeme",
        "placeholder",
        "dummy",
        "test-",
        "test_",
        "fake-",
        "fake_",
        "mock-",
        "mock_",
        "todo",
        "none",
        "null",
        "true",
        "false",
        "http://localhost",
        "https://localhost",
        "${",
        "$",
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
            sanitized_lines.append(updated_line)
        return SanitizationResult(
            sanitized_content="".join(sanitized_lines), redacted_secrets=matches
        )

    @classmethod
    def _apply_token_pattern(
        cls, line: str, line_number: int, pattern_spec: _SecretPattern, matches: list[SecretMatch]
    ) -> str:

        def replace_match(match: re.Match[str]) -> str:
            secret_val = match.group(0)
            placeholder = f"<REDACTED_SECRET:{pattern_spec.kind.value}>"
            matches.append(
                SecretMatch(
                    kind=pattern_spec.kind,
                    line_number=line_number,
                    redacted_placeholder=placeholder,
                    masked_preview=cls._mask_secret(secret_val),
                )
            )
            return placeholder

        return pattern_spec.regex.sub(replace_match, line)

    @classmethod
    def _apply_assignment_pattern(
        cls, line: str, line_number: int, matches: list[SecretMatch]
    ) -> str:

        def replace_match(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            quote = match.group("quote")
            value = match.group("value")
            if cls._is_benign_value(value):
                return match.group(0)
            entropy = cls._shannon_entropy(value)
            if entropy < 3.3 and len(value) < 16:
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
    def _apply_dotenv_pattern(cls, line: str, line_number: int, matches: list[SecretMatch]) -> str:

        def replace_match(match: re.Match[str]) -> str:
            export_prefix = match.group("export") or ""
            key = match.group("key")
            quote = match.group("quote") or ""
            value = match.group("value").strip()
            if cls._is_benign_value(value):
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
    def _is_benign_value(cls, value: str) -> bool:
        stripped = value.strip()
        if len(stripped) < 8:
            return True
        lower = stripped.lower()
        if any(lower.startswith(p.lower()) for p in cls._SAFE_VALUE_PREFIXES):
            return True
        if "<redacted_secret:" in lower:
            return True
        return bool(" " in stripped or stripped.startswith(("/", "./", "../")))

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
