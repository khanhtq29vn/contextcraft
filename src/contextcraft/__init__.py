"""ContextCraft: AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Codebase Compressor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from contextcraft.models import (
    ASTParseError,
    ByteRange,
    CompilationConfig,
    CompilationError,
    CompilationResult,
    CompilationStats,
    ContextCraftError,
    FidelityLevel,
    FileAnalysis,
    InvalidBudgetError,
    OutputFormat,
    RepositoryNotFoundError,
    SecretKind,
    SecretMatch,
    SymbolKind,
    SymbolNode,
)

if TYPE_CHECKING:
    from contextcraft.core import ContextCraft

__version__ = "0.1.0"

__all__ = [
    "ASTParseError",
    "ByteRange",
    "CompilationConfig",
    "CompilationError",
    "CompilationResult",
    "CompilationStats",
    "ContextCraft",
    "ContextCraftError",
    "FidelityLevel",
    "FileAnalysis",
    "InvalidBudgetError",
    "OutputFormat",
    "RepositoryNotFoundError",
    "SecretKind",
    "SecretMatch",
    "SymbolKind",
    "SymbolNode",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Lazy-load `ContextCraft` orchestrator to keep lightweight model imports fast."""
    if name == "ContextCraft":
        from contextcraft.core import ContextCraft

        return ContextCraft
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
