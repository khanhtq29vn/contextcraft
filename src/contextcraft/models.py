from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contextcraft.ast import ParsedAst, Symbol
from contextcraft.elider import FidelityLevel, RenderedTier


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)


class ContextCraftError(Exception):
    pass


class RepositoryNotFoundError(ContextCraftError):
    pass


class InvalidBudgetError(ContextCraftError):
    pass


class ASTParseError(ContextCraftError):
    pass


class CompilationError(ContextCraftError):
    pass


class OutputFormat(StrEnum):
    MARKDOWN = "markdown"
    XML = "xml"
    JSON = "json"


class SecretKind(StrEnum):
    AWS_ACCESS_KEY = "AWS_ACCESS_KEY"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    GOOGLE_API_KEY = "GOOGLE_API_KEY"
    SLACK_TOKEN = "SLACK_TOKEN"
    STRIPE_KEY = "STRIPE_KEY"
    PRIVATE_KEY_BLOCK = "PRIVATE_KEY_BLOCK"
    GENERIC_HIGH_ENTROPY = "GENERIC_SECRET"
    ENV_SECRET_ASSIGNMENT = "ENV_SECRET"


class SecretMatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: SecretKind
    line_number: int = Field(ge=1)
    redacted_placeholder: str
    masked_preview: str = Field()


_BUDGET_SHORTHAND_RE = re.compile("^\\s*(\\d+(?:\\.\\d+)?)\\s*([kKmM]?)\\s*$")


class CompilationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    budget_tokens: int = Field(default=32000, gt=0)
    focus_query: str | None = Field(default=None)
    focus_files: list[str] = Field(default_factory=list)
    output_format: OutputFormat = Field(default=OutputFormat.MARKDOWN)
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    respect_gitignore: bool = Field(default=True)
    redact_secrets: bool = Field(default=True)
    max_file_size_bytes: int = Field(default=1048576, gt=0)
    tokenizer_encoding: str = Field(default="cl100k_base")

    @field_validator("budget_tokens", mode="before")
    @classmethod
    def _coerce_budget_shorthand(cls, value: Any) -> int:
        return cls.parse_budget(value)

    @classmethod
    def parse_budget(cls, raw_budget: str | int) -> int:
        if isinstance(raw_budget, bool) or not isinstance(raw_budget, (str, int)):
            raise InvalidBudgetError(f"Unsupported budget type: {type(raw_budget).__name__}")
        if isinstance(raw_budget, int):
            if raw_budget <= 0:
                raise InvalidBudgetError(f"Token budget must be positive, got {raw_budget}.")
            return raw_budget
        match = _BUDGET_SHORTHAND_RE.match(str(raw_budget))
        if not match:
            raise InvalidBudgetError(
                f"Invalid token budget format '{raw_budget}'. Examples: '16k', '32000', '128k'."
            )
        amount_str, suffix = match.groups()
        whole, _, fractional = amount_str.partition(".")
        multiplier = 1
        if suffix.lower() == "k":
            multiplier = 1000
        elif suffix.lower() == "m":
            multiplier = 1000000
        computed = int(whole) * multiplier
        if fractional:
            computed += int(fractional) * multiplier // (10 ** len(fractional))
        if computed <= 0:
            raise InvalidBudgetError(f"Token budget must be > 0, got {computed}.")
        return computed


class CompilationStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_files_discovered: int = Field(ge=0)
    binary_files_skipped: int = Field(default=0, ge=0)
    ignored_files_skipped: int = Field(default=0, ge=0)
    files_compiled: int = Field(ge=0)
    raw_tokens: int = Field(ge=0)
    compressed_tokens: int = Field(ge=0)
    tree_overhead_tokens: int = Field(default=0, ge=0)
    budget_tokens: int = Field(gt=0)
    budget_utilization_pct: float = Field(ge=0.0)
    compression_ratio: float = Field(ge=0.0)
    token_savings_pct: float = Field()
    fidelity_counts: dict[str, int] = Field(default_factory=dict)
    total_symbols_extracted: int = Field(default=0, ge=0)
    preserved_signatures_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    secrets_redacted: int = Field(default=0, ge=0)
    execution_time_ms: float = Field(ge=0.0)


@dataclass
class FileAnalysis:
    rel_path: str
    abs_path: str
    language: str
    size_bytes: int
    parsed: ParsedAst
    tiers: dict[FidelityLevel, RenderedTier] = field(default_factory=dict)
    pagerank_score: float = 0.0
    relevance_boost: float = 1.0
    selected_fidelity: FidelityLevel = FidelityLevel.TREE
    redacted_secrets: list[SecretMatch] = field(default_factory=list)

    @property
    def symbols(self) -> list[Symbol]:
        return self.parsed.symbols

    @property
    def imports(self) -> list[str]:
        return [self.parsed.text(item.declaration_range) for item in self.parsed.imports]

    @property
    def defined_identifiers(self) -> list[str]:
        return self.parsed.defined_identifiers

    @property
    def referenced_identifiers(self) -> list[str]:
        return self.parsed.referenced_identifiers

    @property
    def raw_tokens(self) -> int:
        return self.tiers[FidelityLevel.FULL].tokens

    @property
    def tier_tokens(self) -> dict[FidelityLevel, int]:
        return {level: tier.tokens for level, tier in self.tiers.items()}

    @property
    def selected_content(self) -> str:
        return self.tiers[self.selected_fidelity].content

    @property
    def selected_tokens(self) -> int:
        return self.tiers[self.selected_fidelity].tokens

    @property
    def redacted_secrets_count(self) -> int:
        return len(self.redacted_secrets)


@dataclass
class CompilationResult:
    root_path: str
    output_format: OutputFormat
    content: str
    stats: CompilationStats
    files: list[FileAnalysis]

    @property
    def markdown(self) -> str:
        return self.content

    @property
    def text_content(self) -> str:
        return self.content
