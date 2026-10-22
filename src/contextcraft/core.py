"""Core orchestration engine and Python SDK entry point for ContextCraft.

Modeled after `microsoft/markitdown`'s clean `MarkItDown` class design,
`ContextCraft` coordinates the 5-stage semantic compression pipeline:
1. `RepositoryScanner`: Gitignore-aware file discovery and binary filtering.
2. `SecretSanitizer`: Pre-AST credential and high-entropy secret scrubbing.
3. `UniversalASTParser`: Multi-language Tree-sitter symbol and reference extraction.
4. `DependencyGraphScorer`: Cross-file graph construction and Personalized PageRank.
5. `MultiResolutionElider`, `TokenBudgetOptimizer` & `ArtifactFormatter`:
   4-tier AST pruning, Multiple-Choice Knapsack optimization, and strict-budget rendering.
"""

from __future__ import annotations

import time
from pathlib import Path

from contextcraft.ast_parser import UniversalASTParser
from contextcraft.elider import MultiResolutionElider, TokenCounter
from contextcraft.formatter import ArtifactFormatter
from contextcraft.graph import DependencyGraphScorer
from contextcraft.models import (
    CompilationConfig,
    CompilationResult,
    FileAnalysis,
    OutputFormat,
)
from contextcraft.optimizer import TokenBudgetOptimizer
from contextcraft.sanitizer import SecretSanitizer
from contextcraft.scanner import RepositoryScanner, ScanOutcome


class ContextCraft:
    """AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Codebase Compressor.

    Example:
        ```python
        from contextcraft import ContextCraft

        cc = ContextCraft(budget_tokens="32k")
        result = cc.compile("./my-repo", focus_query="authentication middleware")
        print(result.markdown)
        print(result.stats.compression_ratio)
        ```
    """

    def __init__(
        self,
        config: CompilationConfig | None = None,
        *,
        budget_tokens: int | str = 32_000,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
        output_format: OutputFormat | str = OutputFormat.MARKDOWN,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        respect_gitignore: bool = True,
        redact_secrets: bool = True,
        max_file_size_bytes: int = 1_048_576,
        tokenizer_encoding: str = "cl100k_base",
    ) -> None:
        """Initialize the ContextCraft compiler with default or custom configuration."""
        if config is not None:
            self.config = config.model_copy(deep=True)
        else:
            resolved_format = (
                output_format
                if isinstance(output_format, OutputFormat)
                else OutputFormat(output_format.lower())
            )
            self.config = CompilationConfig(
                budget_tokens=CompilationConfig.parse_budget(budget_tokens),
                focus_query=focus_query,
                focus_files=list(focus_files) if focus_files else [],
                output_format=resolved_format,
                include_patterns=list(include_patterns) if include_patterns else [],
                exclude_patterns=list(exclude_patterns) if exclude_patterns else [],
                respect_gitignore=respect_gitignore,
                redact_secrets=redact_secrets,
                max_file_size_bytes=max_file_size_bytes,
                tokenizer_encoding=tokenizer_encoding,
            )

    def compile(
        self,
        repo_path: str | Path,
        *,
        budget_tokens: int | str | None = None,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
        output_format: OutputFormat | str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        redact_secrets: bool | None = None,
    ) -> CompilationResult:
        """Compile a target repository into a token-budgeted context artifact.

        Per-call keyword arguments override the instance's default `CompilationConfig`
        without mutating the instance state.
        """
        start_perf = time.perf_counter()
        effective_config = self._build_effective_config(
            budget_tokens=budget_tokens,
            focus_query=focus_query,
            focus_files=focus_files,
            output_format=output_format,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            redact_secrets=redact_secrets,
        )

        scan_outcome, analyses = self._ingest_and_analyze(repo_path, effective_config)

        token_counter = TokenCounter(effective_config.tokenizer_encoding)
        elider = MultiResolutionElider(token_counter)
        elider.process_files(analyses)

        scorer = DependencyGraphScorer(effective_config)
        scorer.score_files(analyses)

        # Estimate directory tree token overhead before running the MCKP solver
        initial_tree = ArtifactFormatter.render_directory_tree(
            analyses,
            root_name=scan_outcome.root_path.name,
        )
        tree_overhead = (
            TokenBudgetOptimizer.BASE_DOCUMENT_OVERHEAD_TOKENS
            + token_counter.count(initial_tree)
        )

        optimizer = TokenBudgetOptimizer(effective_config)
        optimizer.optimize(analyses, tree_overhead_tokens=tree_overhead)

        elapsed_ms = (time.perf_counter() - start_perf) * 1000.0
        formatter = ArtifactFormatter(effective_config, token_counter)
        return formatter.format_result(
            root_path=scan_outcome.root_path,
            files=analyses,
            total_files_discovered=scan_outcome.total_files_discovered,
            binary_files_skipped=scan_outcome.binary_files_skipped,
            ignored_files_skipped=scan_outcome.ignored_files_skipped,
            execution_time_ms=elapsed_ms,
        )

    def analyze_repository(
        self,
        repo_path: str | Path,
        *,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
    ) -> list[FileAnalysis]:
        """Run scanning, sanitization, AST extraction, PageRank, and tier elision without formatting."""
        effective_config = self._build_effective_config(
            focus_query=focus_query,
            focus_files=focus_files,
        )
        _, analyses = self._ingest_and_analyze(repo_path, effective_config)
        token_counter = TokenCounter(effective_config.tokenizer_encoding)
        MultiResolutionElider(token_counter).process_files(analyses)
        DependencyGraphScorer(effective_config).score_files(analyses)
        return analyses

    def _ingest_and_analyze(
        self,
        repo_path: str | Path,
        config: CompilationConfig,
    ) -> tuple[ScanOutcome, list[FileAnalysis]]:
        """Execute Stage 1 (Scanner & Sanitizer) and Stage 2 (Tree-sitter AST Parser)."""
        scanner = RepositoryScanner(config)
        scan_outcome = scanner.scan(repo_path)

        analyses: list[FileAnalysis] = []
        for scanned in scan_outcome.files:
            if config.redact_secrets:
                sanitized_res = SecretSanitizer.sanitize_detailed(
                    scanned.raw_content,
                    file_path=scanned.rel_path,
                )
                clean_text = sanitized_res.sanitized_content
                redacted_list = sanitized_res.redacted_secrets
            else:
                clean_text = scanned.raw_content
                redacted_list = []

            ast_res = UniversalASTParser.parse_detailed(clean_text, scanned.language)
            analyses.append(
                FileAnalysis(
                    rel_path=scanned.rel_path,
                    abs_path=scanned.abs_path,
                    language=scanned.language,
                    size_bytes=scanned.size_bytes,
                    raw_content=scanned.raw_content,
                    sanitized_content=clean_text,
                    symbols=ast_res.symbols,
                    defined_identifiers=ast_res.defined_identifiers,
                    referenced_identifiers=ast_res.referenced_identifiers,
                    imports=ast_res.imports,
                    redacted_secrets=redacted_list,
                )
            )

        return scan_outcome, analyses

    def _build_effective_config(
        self,
        *,
        budget_tokens: int | str | None = None,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
        output_format: OutputFormat | str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        redact_secrets: bool | None = None,
    ) -> CompilationConfig:
        """Clone `self.config` and apply any non-None per-call overrides."""
        cfg = self.config.model_copy(deep=True)
        if budget_tokens is not None:
            cfg.budget_tokens = CompilationConfig.parse_budget(budget_tokens)
        if focus_query is not None:
            cfg.focus_query = focus_query
        if focus_files is not None:
            cfg.focus_files = list(focus_files)
        if output_format is not None:
            cfg.output_format = (
                output_format
                if isinstance(output_format, OutputFormat)
                else OutputFormat(output_format.lower())
            )
        if include_patterns is not None:
            cfg.include_patterns = list(include_patterns)
        if exclude_patterns is not None:
            cfg.exclude_patterns = list(exclude_patterns)
        if redact_secrets is not None:
            cfg.redact_secrets = redact_secrets
        return cfg
