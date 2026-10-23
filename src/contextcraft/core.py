from __future__ import annotations

import time
from pathlib import Path

from contextcraft.ast import ParsedAst
from contextcraft.ast.parser import parse
from contextcraft.elider import Elider, TokenCounter
from contextcraft.formatter import ArtifactFormatter
from contextcraft.graph import DependencyGraphScorer
from contextcraft.languages.base import Language
from contextcraft.languages.builtin import TextLanguage, default_registry
from contextcraft.languages.registry import LanguageRegistry
from contextcraft.models import CompilationConfig, CompilationResult, FileAnalysis, OutputFormat
from contextcraft.optimizer import TokenBudgetOptimizer
from contextcraft.sanitizer import SecretSanitizer
from contextcraft.scanner import RepositoryScanner, ScanOutcome


class ContextCraft:
    def __init__(
        self,
        config: CompilationConfig | None = None,
        *,
        registry: LanguageRegistry | None = None,
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
        self.registry = registry if registry is not None else default_registry()
        self.config = (
            config.model_copy(deep=True)
            if config is not None
            else CompilationConfig(
                budget_tokens=CompilationConfig.parse_budget(budget_tokens),
                focus_query=focus_query,
                focus_files=list(focus_files or []),
                output_format=OutputFormat(output_format.lower()),
                include_patterns=list(include_patterns or []),
                exclude_patterns=list(exclude_patterns or []),
                respect_gitignore=respect_gitignore,
                redact_secrets=redact_secrets,
                max_file_size_bytes=max_file_size_bytes,
                tokenizer_encoding=tokenizer_encoding,
            )
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
        start = time.perf_counter()
        config = self._effective_config(
            budget_tokens=budget_tokens,
            focus_query=focus_query,
            focus_files=focus_files,
            output_format=output_format,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            redact_secrets=redact_secrets,
        )
        outcome, files, counter = self._analyze(repo_path, config)
        formatter = ArtifactFormatter(config, counter)
        tree = formatter.render_budgeted_directory_tree(files, outcome.root_path.name)
        overhead = TokenBudgetOptimizer.BASE_DOCUMENT_OVERHEAD_TOKENS + counter.count(tree)
        TokenBudgetOptimizer(config).optimize(files, tree_overhead_tokens=overhead)
        result = formatter.format_result(
            root_path=outcome.root_path,
            files=files,
            total_files_discovered=outcome.total_files_discovered,
            binary_files_skipped=outcome.binary_files_skipped,
            ignored_files_skipped=outcome.ignored_files_skipped,
            execution_time_ms=0.0,
        )
        result.stats.execution_time_ms = (time.perf_counter() - start) * 1000
        return result

    def analyze_repository(
        self,
        repo_path: str | Path,
        *,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
    ) -> list[FileAnalysis]:
        config = self._effective_config(focus_query=focus_query, focus_files=focus_files)
        return self._analyze(repo_path, config)[1]

    def _analyze(
        self,
        repo_path: str | Path,
        config: CompilationConfig,
    ) -> tuple[ScanOutcome, list[FileAnalysis], TokenCounter]:
        outcome = RepositoryScanner(self.registry, config).scan(repo_path)
        counter = TokenCounter(config.tokenizer_encoding)
        elider = Elider(counter)
        files: list[FileAnalysis] = []
        for scanned in outcome.files:
            content = scanned.source.decode("utf-8")
            sanitized = (
                SecretSanitizer.sanitize_detailed(content, scanned.rel_path)
                if config.redact_secrets
                else None
            )
            source = (
                sanitized.sanitized_content.encode("utf-8")
                if sanitized is not None
                else scanned.source
            )
            language: type[Language] = TextLanguage
            parsed = ParsedAst(source=source)
            for index, candidate in enumerate(scanned.candidates):
                candidate_ast = parse(source, candidate)
                if index == 0 or not candidate_ast.has_errors:
                    language, parsed = candidate, candidate_ast
                if not candidate_ast.has_errors:
                    break
            files.append(
                FileAnalysis(
                    rel_path=scanned.rel_path,
                    abs_path=scanned.abs_path,
                    language=language.spec.id,
                    size_bytes=scanned.size_bytes,
                    parsed=parsed,
                    tiers=elider.render(parsed, language),
                    redacted_secrets=sanitized.redacted_secrets if sanitized is not None else [],
                )
            )
        DependencyGraphScorer(config).score_files(files)
        return outcome, files, counter

    def _effective_config(
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
        config = self.config.model_copy(deep=True)
        if budget_tokens is not None:
            config.budget_tokens = CompilationConfig.parse_budget(budget_tokens)
        if focus_query is not None:
            config.focus_query = focus_query
        if focus_files is not None:
            config.focus_files = list(focus_files)
        if output_format is not None:
            config.output_format = OutputFormat(output_format.lower())
        if include_patterns is not None:
            config.include_patterns = list(include_patterns)
        if exclude_patterns is not None:
            config.exclude_patterns = list(exclude_patterns)
        if redact_secrets is not None:
            config.redact_secrets = redact_secrets
        return config
