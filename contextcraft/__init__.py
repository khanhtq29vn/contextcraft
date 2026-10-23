from __future__ import annotations

from contextcraft.ast import ByteRange, Import, ParsedAst, Symbol
from contextcraft.core import AnalyzedRepository, ContextCraft
from contextcraft.elider import Elider, FidelityLevel, RenderedTier, TokenCounter
from contextcraft.languages.builtin import default_registry
from contextcraft.languages.registry import LanguageRegistry
from contextcraft.models import (
    ASTParseError,
    CompilationConfig,
    CompilationError,
    CompilationResult,
    CompilationStats,
    ContextCraftError,
    FileAnalysis,
    InvalidBudgetError,
    OutputFormat,
    RepositoryNotFoundError,
    SecretKind,
    SecretMatch,
)
from contextcraft.utils import get_version

__version__ = get_version()

__all__ = [
    "ASTParseError",
    "AnalyzedRepository",
    "ByteRange",
    "CompilationConfig",
    "CompilationError",
    "CompilationResult",
    "CompilationStats",
    "ContextCraft",
    "ContextCraftError",
    "Elider",
    "FidelityLevel",
    "FileAnalysis",
    "Import",
    "InvalidBudgetError",
    "LanguageRegistry",
    "OutputFormat",
    "ParsedAst",
    "RenderedTier",
    "RepositoryNotFoundError",
    "SecretKind",
    "SecretMatch",
    "Symbol",
    "TokenCounter",
    "__version__",
    "default_registry",
]
