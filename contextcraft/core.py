"""Compile repository source into a token-budgeted context artifact."""

from __future__ import annotations

from pathlib import Path

from contextcraft.config import Config
from contextcraft.formatter import ArtifactFormatter
from contextcraft.graph import GraphBuilder, GraphScorer
from contextcraft.imports import ImportResolver
from contextcraft.index import Indexer
from contextcraft.languages import BUILTIN_LANGUAGES
from contextcraft.languages.base import Language
from contextcraft.models import Artifact
from contextcraft.optimizer import BudgetAllocator
from contextcraft.source import SourceLoader
from contextcraft.tiers import TierRenderer


class ContextCraft:
    """Analyze a repository and fit its source into a token-budgeted artifact.

    Args:
        config: Options shared by all pipeline stages. Uses defaults when
            omitted. The compiler uses the supplied instance without copying it.
        languages: Language classes used for file detection, source analysis,
            import resolution, ranking, and tier rendering.

    Example:
        compiler = ContextCraft(Config(budget_tokens=8000))
        artifact = compiler.compile(".")
        print(artifact.content)
    """

    def __init__(
        self,
        config: Config | None = None,
        *,
        languages: tuple[type[Language], ...] = BUILTIN_LANGUAGES,
    ) -> None:
        self.config = config if config is not None else Config()
        self.languages = languages

    def compile(self, path: str | Path) -> Artifact:
        """Compile repository context within the configured token budget.

        Args:
            path: Directory to scan, or a file whose parent directory will be scanned.

        Returns:
            An artifact with the formatted context, token count, and final
            file tiers. Each call reads and analyzes the repository again
            without modifying source files. The output fits the token budget
            unless the artifact reports estimated counts.

        Raises:
            OSError: If the repository path or an indexed file cannot be read.
            ValueError: If the budget is invalid or too small for output framing,
                or the tokenizer encoding is invalid.

        Pipeline and dependency errors propagate to the caller.
        """
        config = self.config
        index = Indexer(languages=self.languages).index(path, config)
        source = SourceLoader().load(index, config)
        resolutions = ImportResolver().resolve(index, source)
        graph = GraphBuilder().build(index, source, resolutions)
        scores = GraphScorer().score(index, source, graph, config)
        tiers = TierRenderer().render(index, source, config)
        selection = BudgetAllocator().allocate(index, tiers, scores, config)

        return ArtifactFormatter().format(index, tiers, scores, selection, config)
