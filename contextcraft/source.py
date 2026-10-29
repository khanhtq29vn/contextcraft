"""Load text sources and extract language-specific metadata."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

from contextcraft.config import Config
from contextcraft.models import FileAnalysis, Index, Source

_BINARY_CONTROL_RE = re.compile(rb"[\x00-\x08\x0b\x0e-\x1f]")

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
            config: File-size limit, secret-redaction setting, and worker count.

        Returns:
            Source bytes and extracted metadata for eligible files. Files that
            exceed the size limit, contain binary control bytes, or are not valid
            UTF-8 are skipped. Redaction preserves byte offsets and line endings,
            but it does not guarantee that every secret is detected.

        Raises:
            ValueError: If the worker count is not positive.
            OSError: If an indexed file cannot be opened or read.
            KeyError: If a loaded file has a language ID absent from index.languages.
        """
        if config.workers <= 0:
            raise ValueError("Worker count must be positive")

        content = {}
        docstrings = {}
        imports = []
        analyses = {}
        limit = config.max_file_size_bytes

        def load_file(
            file_id: int,
        ) -> tuple[bytes, FileAnalysis | None] | None:
            file = index.files[file_id]
            with file.path.open("rb") as stream:
                source = stream.read(limit + 1)

            if len(source) > limit or _BINARY_CONTROL_RE.search(source):
                return None

            try:
                source.decode("utf-8")
            except UnicodeDecodeError:
                return None

            if config.redact_secrets:
                for pattern in _SECRET_PATTERNS:
                    source = pattern.sub(_mask_secret, source)

            language = (
                index.languages[file.language_id]
                if file.language_id is not None
                else None
            )

            analysis = (
                language.analyze(source, file_id) if language is not None else None
            )

            return source, analysis

        file_ids = sorted(index.files)

        with (
            ThreadPoolExecutor(max_workers=config.workers)
            if config.workers > 1
            else nullcontext()
        ) as executor:
            results = (
                executor.map(load_file, file_ids)
                if executor is not None
                else map(load_file, file_ids)
            )

            for file_id, result in zip(file_ids, results):
                if result is None:
                    continue

                source, analysis = result
                content[file_id] = source

                if analysis is not None:
                    docstrings[file_id] = analysis.docstrings
                    imports.extend(analysis.imports)
                    analyses[file_id] = analysis

        return Source(
            content=content,
            docstrings=docstrings,
            imports=tuple(imports),
            analyses=analyses,
        )
