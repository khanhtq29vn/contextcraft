"""Load text sources and extract language-specific metadata."""

from __future__ import annotations

import re

from contextcraft.config import Config
from contextcraft.models import Index, Source

_SECRET_PATTERNS = (
    re.compile(
        rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----"
    ),
    re.compile(
        rb"\b(?:sk-(?:ant-|proj-|svcacct-)?[A-Za-z0-9_-]{20,}"
        rb"|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}"
        rb"|(?:AKIA|ASIA)[A-Z0-9]{16}"
        rb"|AIza[A-Za-z0-9_-]{35}"
        rb"|xox[baprs]-[A-Za-z0-9-]{10,})\b"
    ),
    re.compile(
        rb"\bBearer\s+(?P<value>[A-Za-z0-9._~+/-]{16,}=*)",
        re.IGNORECASE,
    ),
    re.compile(
        rb"\b[\w-]*(?:api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)"
        rb"[\w-]*[\"']?\s*[:=]\s*(?P<quote>[\"'])"
        rb"(?P<value>(?:\\[^\r\n]|(?!(?P=quote))[^\r\n\\])*)(?P=quote)",
        re.IGNORECASE,
    ),
)


def _mask_secret(match: re.Match[bytes]) -> bytes:
    start, end = match.span("value") if "value" in match.re.groupindex else match.span()
    content = match.group()
    start -= match.start()
    end -= match.start()

    # Preserve line endings and byte offsets for downstream parsing.
    return (
        content[:start] + re.sub(rb"[^\r\n]", b"x", content[start:end]) + content[end:]
    )


class SourceLoader:
    """Load indexed source files and analyze them with their detected languages."""

    def load(self, index: Index, config: Config) -> Source:
        """Read eligible files and optionally redact recognized secrets.

        Args:
            index: Files to read, keyed by pipeline file ID.
            config: File-size limit and secret-redaction setting.

        Returns:
            Source bytes and extracted metadata for eligible files. Files that
            exceed the size limit, contain binary control bytes, or are not valid
            UTF-8 are skipped. Redaction preserves byte offsets and line endings,
            but it does not guarantee that every secret is detected.

        Raises:
            OSError: If an indexed file cannot be opened or read.
            KeyError: If a loaded file has a language ID absent from index.languages.
        """
        content = {}
        docstrings = {}
        imports = []
        limit = config.max_file_size_bytes

        for file_id, file in sorted(index.files.items()):
            with file.path.open("rb") as stream:
                source = stream.read(limit + 1)

            if len(source) > limit or any(
                byte < 32 and byte not in (9, 10, 12, 13) for byte in source
            ):
                continue

            try:
                source.decode("utf-8")
            except UnicodeDecodeError:
                continue

            if config.redact_secrets:
                for pattern in _SECRET_PATTERNS:
                    source = pattern.sub(_mask_secret, source)

            content[file_id] = source
            language = (
                index.languages[file.language_id]
                if file.language_id is not None
                else None
            )

            if language is not None:
                docstrings[file_id] = language.extract_docstrings(source)
                imports.extend(language.extract_imports(source, file_id))

        return Source(content=content, docstrings=docstrings, imports=tuple(imports))
