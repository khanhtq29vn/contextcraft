"""Core domain models, enums, and exception hierarchy for ContextCraft.

This module defines the typed data structures shared across the 5-stage
ContextCraft pipeline:
1. RepositoryScanner & SecretSanitizer
2. UniversalASTParser
3. DependencyGraphScorer (Personalized PageRank)
4. MultiResolutionElider (4-tier AST pruning)
5. TokenBudgetOptimizer (Multiple-Choice Knapsack solver) & ArtifactFormatter
"""

from __future__ import annotations

import re
from enum import Enum, IntEnum
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrEnum(str, Enum):
    """Compatibility string enum supporting Python 3.10+."""

    def __str__(self) -> str:
        return str(self.value)


# ============================================================================
# Exception Hierarchy (Modeled after microsoft/markitdown)
# ============================================================================


class ContextCraftError(Exception):
    """Base exception for all ContextCraft errors."""


class RepositoryNotFoundError(ContextCraftError):
    """Raised when the target repository path does not exist or is not a directory."""


class InvalidBudgetError(ContextCraftError):
    """Raised when a user supplies an invalid or non-positive token budget."""


class ASTParseError(ContextCraftError):
    """Raised when unrecoverable errors occur during AST analysis."""


class CompilationError(ContextCraftError):
    """Raised when the context compilation pipeline fails to produce an artifact."""


# ============================================================================
# Core Enumerations
# ============================================================================


class FidelityLevel(IntEnum):
    r"""Discrete AST resolution tiers for each file in the repository.

    Every file $i$ in the repository is rendered at all 4 fidelity tiers, and
    the Knapsack optimizer selects exactly one tier $l_i \in \{0, 1, 2, 3\}$
    to maximize architectural signal within the token budget $B$.
    """

    TREE_ONLY = 0
    SIGNATURES_ONLY = 1
    SKELETON_WITH_DOCSTRINGS = 2
    FULL_SOURCE = 3

    @property
    def badge(self) -> str:
        """Compact 4-letter badge used in directory trees and CLI tables."""
        badges = {
            FidelityLevel.TREE_ONLY: "TREE",
            FidelityLevel.SIGNATURES_ONLY: "SIGS",
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: "SKEL",
            FidelityLevel.FULL_SOURCE: "FULL",
        }
        return badges[self]

    @property
    def label(self) -> str:
        """Human-readable label describing the fidelity tier."""
        labels = {
            FidelityLevel.TREE_ONLY: "Tree Entry Only",
            FidelityLevel.SIGNATURES_ONLY: "Public Signatures Only",
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: "AST Skeleton + Docstrings",
            FidelityLevel.FULL_SOURCE: "Full Source Code",
        }
        return labels[self]

    @property
    def semantic_utility(self) -> float:
        r"""Normalized information utility $u(l) \in [0.0, 1.0]$ used by the MCKP solver.

        Note the concave utility curve: retaining AST signatures and docstrings
        (`SKELETON_WITH_DOCSTRINGS`) captures 82% of architectural comprehension
        value typically at a fraction of the token cost of full implementation bodies.
        """
        utilities = {
            FidelityLevel.TREE_ONLY: 0.0,
            FidelityLevel.SIGNATURES_ONLY: 0.45,
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: 0.82,
            FidelityLevel.FULL_SOURCE: 1.00,
        }
        return utilities[self]


class OutputFormat(StrEnum):
    """Supported target output formats for compiled repository context."""

    MARKDOWN = "markdown"
    XML = "xml"
    JSON = "json"


class SecretKind(StrEnum):
    """Categories of sensitive secrets automatically scrubbed before emission."""

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


# ============================================================================
# AST & Security Data Models
# ============================================================================


class ByteRange(BaseModel):
    """Zero-indexed byte and one-indexed line span within a UTF-8 source buffer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_byte: int = Field(ge=0, description="Inclusive start byte offset in UTF-8 content.")
    end_byte: int = Field(ge=0, description="Exclusive end byte offset in UTF-8 content.")
    start_line: int = Field(ge=1, description="1-indexed inclusive start line number.")
    end_line: int = Field(ge=1, description="1-indexed inclusive end line number.")

    @model_validator(mode="after")
    def _validate_Ordering(self) -> ByteRange:
        if self.end_byte < self.start_byte:
            raise ValueError(
                f"end_byte ({self.end_byte}) must be >= start_byte ({self.start_byte})"
            )
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        return self

    @property
    def byte_length(self) -> int:
        """Total byte length of the span."""
        return self.end_byte - self.start_byte

    @property
    def line_count(self) -> int:
        """Total number of lines spanned."""
        return self.end_line - self.start_line + 1


class SecretMatch(BaseModel):
    """Metadata record for a single redacted secret within a source file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SecretKind
    line_number: int = Field(ge=1)
    redacted_placeholder: str
    masked_preview: str = Field(
        description="Safe masked preview (e.g., 'sk-p...mnop') for audit diagnostics."
    )


class SymbolNode(BaseModel):
    """Represents a structural symbol extracted via Tree-sitter or fallback AST parsing."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(min_length=1, description="Unqualified identifier name.")
    qualified_name: str | None = Field(
        default=None, description="Fully scoped symbol name (e.g., 'AuthService.verify_token')."
    )
    kind: str = Field(min_length=1, description="Language-defined symbol category.")
    signature: str = Field(
        description="Clean header/declaration line(s) including type annotations."
    )
    docstring: str | None = Field(
        default=None, description="Extracted docstring or preceding doc-comment block."
    )
    full_range: ByteRange = Field(description="Byte/line span of the entire symbol definition.")
    body_range: ByteRange | None = Field(
        default=None,
        description="Language-selected byte/line span to elide in Tier 2.",
    )
    is_exported: bool = Field(
        default=True,
        description="False for private/internal symbols (e.g., leading underscore).",
    )
    parent_symbol: str | None = Field(
        default=None, description="Qualified enclosing scope name if nested."
    )
    decorators: list[str] = Field(
        default_factory=list, description="Attached decorators or attributes."
    )


class ASTParseResult(NamedTuple):
    """Structural analysis of a single source file."""

    symbols: list[SymbolNode]
    imports: list[str]
    defined_identifiers: list[str]
    referenced_identifiers: list[str]


# ============================================================================
# File & Repository Compilation Models
# ============================================================================


class FileAnalysis(BaseModel):
    """Complete analysis state for a single source file across the compilation pipeline."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    rel_path: str = Field(description="POSIX-normalized path relative to repository root.")
    abs_path: str = Field(description="Resolved absolute filesystem path.")
    language: str = Field(
        description="Canonical language identifier (e.g., 'python', 'typescript')."
    )
    size_bytes: int = Field(ge=0)
    raw_content: str = Field(repr=False)
    sanitized_content: str = Field(repr=False)
    raw_tokens: int = Field(default=0, ge=0)

    symbols: list[SymbolNode] = Field(default_factory=list)
    defined_identifiers: list[str] = Field(default_factory=list)
    referenced_identifiers: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)

    pagerank_score: float = Field(default=0.0, ge=0.0)
    relevance_boost: float = Field(default=1.0, ge=0.0)

    rendered_tiers: dict[FidelityLevel, str] = Field(default_factory=dict, repr=False)
    tier_tokens: dict[FidelityLevel, int] = Field(default_factory=dict)
    selected_fidelity: FidelityLevel = Field(default=FidelityLevel.TREE_ONLY)

    redacted_secrets: list[SecretMatch] = Field(default_factory=list)

    @property
    def redacted_secrets_count(self) -> int:
        """Total number of secrets scrubbed from this file."""
        return len(self.redacted_secrets)

    @property
    def selected_content(self) -> str:
        """Rendered text corresponding to the optimizer's chosen fidelity tier."""
        return self.rendered_tiers.get(self.selected_fidelity, "")

    @property
    def selected_tokens(self) -> int:
        """Token cost of the optimizer's chosen fidelity tier."""
        return self.tier_tokens.get(self.selected_fidelity, 0)


_BUDGET_SHORTHAND_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kKmM]?)\s*$")


class CompilationConfig(BaseModel):
    """Configuration parameters controlling the ContextCraft compilation pipeline."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    budget_tokens: int = Field(
        default=32_000,
        gt=0,
        description="Strict upper bound on total tokens in the compiled output.",
    )
    focus_query: str | None = Field(
        default=None,
        description="Natural language query or symbol keywords to bias Personalized PageRank.",
    )
    focus_files: list[str] = Field(
        default_factory=list,
        description="Relative file paths or globs to prioritize during PageRank personalization.",
    )
    output_format: OutputFormat = Field(default=OutputFormat.MARKDOWN)
    include_patterns: list[str] = Field(
        default_factory=list,
        description="Optional glob patterns restricting which files are scanned.",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Additional glob patterns to exclude beyond .gitignore and defaults.",
    )
    respect_gitignore: bool = Field(default=True)
    redact_secrets: bool = Field(default=True)
    max_file_size_bytes: int = Field(
        default=1_048_576,
        gt=0,
        description="Maximum size in bytes for a single text file (default 1 MiB).",
    )
    tokenizer_encoding: str = Field(
        default="cl100k_base",
        description="Tiktoken encoding name used for token accounting.",
    )

    @field_validator("budget_tokens", mode="before")
    @classmethod
    def _coerce_budget_shorthand(cls, value: Any) -> int:
        if isinstance(value, int):
            if value <= 0:
                raise InvalidBudgetError(f"Token budget must be positive, got {value}.")
            return value
        if isinstance(value, str):
            return cls.parse_budget(value)
        raise InvalidBudgetError(f"Unsupported budget type: {type(value).__name__}")

    @classmethod
    def parse_budget(cls, raw_budget: str | int) -> int:
        """Parse human-friendly token budget strings like '16k', '32K', '1.5m', or '8000'."""
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
        amount = float(amount_str)
        multiplier = 1
        if suffix.lower() == "k":
            multiplier = 1_000
        elif suffix.lower() == "m":
            multiplier = 1_000_000

        computed = int(amount * multiplier)
        if computed <= 0:
            raise InvalidBudgetError(f"Token budget must be > 0, got {computed}.")
        return computed


class CompilationStats(BaseModel):
    """Quantitative telemetry and compression metrics for a compilation run."""

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
    compression_ratio: float = Field(
        ge=0.0,
        description="Ratio of raw_tokens / max(compressed_tokens, 1) (e.g., 4.5x).",
    )
    token_savings_pct: float = Field(
        description="Percentage reduction from raw_tokens to compressed_tokens."
    )

    fidelity_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of FidelityLevel badge ('FULL', 'SKEL', 'SIGS', 'TREE') to file count.",
    )
    total_symbols_extracted: int = Field(default=0, ge=0)
    preserved_signatures_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    secrets_redacted: int = Field(default=0, ge=0)
    execution_time_ms: float = Field(ge=0.0)


class CompilationResult(BaseModel):
    """Final immutable output returned by `ContextCraft.compile()`."""

    model_config = ConfigDict(extra="forbid")

    root_path: str
    output_format: OutputFormat
    content: str
    stats: CompilationStats
    files: list[FileAnalysis]

    @property
    def markdown(self) -> str:
        """Ergonomic alias returning the compiled text artifact."""
        return self.content

    @property
    def text_content(self) -> str:
        """Compatibility alias matching `microsoft/markitdown`'s `DocumentConverterResult`."""
        return self.content
