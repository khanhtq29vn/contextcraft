"""ContextCraft: AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Codebase Compressor."""

from __future__ import annotations

from contextcraft.core import ContextCraft
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
    SymbolNode,
)

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
    "SymbolNode",
    "__version__",
]
