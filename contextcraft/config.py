"""Configure repository analysis, token accounting, and artifact output."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import msgspec


class OutputFormat(str, Enum):
    """Choose the artifact serialization format."""

    MARKDOWN = "markdown"
    XML = "xml"
    JSON = "json"


class TokenizerEncoding(str, Enum):
    """Choose a tiktoken encoding for source and output token counts."""

    GPT2 = "gpt2"
    R50K_BASE = "r50k_base"
    P50K_BASE = "p50k_base"
    P50K_EDIT = "p50k_edit"
    CL100K_BASE = "cl100k_base"
    O200K_BASE = "o200k_base"
    O200K_HARMONY = "o200k_harmony"


class Config(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    """Set options shared by the repository pipeline.

    The budget counts tokens, not characters. Focus queries and file patterns
    change file rankings without excluding files; exclude patterns remove files
    during indexing. Secrets are redacted before source analysis when enabled.

    Token estimates cannot guarantee an exact budget. msgspec validates field
    constraints during decoding or conversion, but not direct construction.
    """

    budget_tokens: Annotated[int, msgspec.Meta(gt=0)] = 16000
    focus_query: str | None = None
    focus_files: list[str] = msgspec.field(default_factory=list)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    exclude_patterns: list[str] = msgspec.field(default_factory=list)
    respect_gitignore: bool = True
    redact_secrets: bool = True
    max_file_size_bytes: Annotated[int, msgspec.Meta(gt=0)] = 1048576
    tokenizer_encoding: TokenizerEncoding = TokenizerEncoding.CL100K_BASE
    allow_token_estimates: bool = False
