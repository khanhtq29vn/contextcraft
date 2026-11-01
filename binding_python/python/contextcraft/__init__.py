"""AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.

Create a Config, pass it to ContextCraft, and call run() on a local directory.
The returned RepositoryAnalysis contains the final artifact and pipeline data.
"""

from .contextcraft import (
    Analysis,
    Artifact,
    Config,
    ContextCraft,
    FidelityLevel,
    File,
    FileTiers,
    Graph,
    Index,
    OutputFormat,
    Package,
    PackageDependency,
    RenderedTier,
    Repository,
    RepositoryAnalysis,
    Source,
    Tiers,
    TokenCounter,
    TokenizerEncoding,
    Workspace,
    __version__,
)

__all__ = [
    "Analysis",
    "Artifact",
    "Config",
    "ContextCraft",
    "FidelityLevel",
    "File",
    "FileTiers",
    "Graph",
    "Index",
    "OutputFormat",
    "Package",
    "PackageDependency",
    "RenderedTier",
    "Repository",
    "RepositoryAnalysis",
    "Source",
    "Tiers",
    "TokenCounter",
    "TokenizerEncoding",
    "Workspace",
    "__version__",
]
