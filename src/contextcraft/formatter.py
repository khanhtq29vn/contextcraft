"""Multi-format artifact renderer and strict token-budget post-verifier.

Renders the compiled repository context into:
1. `OutputFormat.MARKDOWN`: High-signal Markdown document with an Executive Summary,
   an ASCII Directory Tree annotated with fidelity badges (`[FULL]`, `[SKEL]`,
   `[SIGS]`, `[TREE]`) and PageRank centrality percentages, and syntax-highlighted
   code blocks ordered by architectural importance.
2. `OutputFormat.XML`: Anthropic Claude-optimized `<repository_context>` XML format.
3. `OutputFormat.JSON`: Structured JSON payload for programmatic RAG and Agent pipelines.

Includes a deterministic budget enforcement loop that guarantees the final emitted
artifact never exceeds `config.budget_tokens`.
"""

from __future__ import annotations

import json
from html import escape as xml_escape
from pathlib import Path
from typing import Any, ClassVar

from contextcraft.elider import TokenCounter
from contextcraft.models import (
    CompilationConfig,
    CompilationResult,
    CompilationStats,
    FidelityLevel,
    FileAnalysis,
    OutputFormat,
)


class ArtifactFormatter:
    """Renders `FileAnalysis` results into Markdown, XML, or JSON within budget."""

    _STEP_DOWN_MAP: ClassVar[dict[FidelityLevel, FidelityLevel]] = {
        FidelityLevel.FULL_SOURCE: FidelityLevel.SKELETON_WITH_DOCSTRINGS,
        FidelityLevel.SKELETON_WITH_DOCSTRINGS: FidelityLevel.SIGNATURES_ONLY,
        FidelityLevel.SIGNATURES_ONLY: FidelityLevel.TREE_ONLY,
        FidelityLevel.TREE_ONLY: FidelityLevel.TREE_ONLY,
    }

    def __init__(
        self,
        config: CompilationConfig | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        """Initialize the formatter with compilation config and token counter."""
        self.config = config or CompilationConfig()
        self.token_counter = token_counter or TokenCounter(self.config.tokenizer_encoding)

    def format_result(
        self,
        *,
        root_path: str | Path,
        files: list[FileAnalysis],
        total_files_discovered: int,
        binary_files_skipped: int,
        ignored_files_skipped: int,
        execution_time_ms: float,
    ) -> CompilationResult:
        """Render the final output string, enforce the token budget, and compute stats."""
        resolved_root_str = str(Path(root_path).resolve())

        # Enforce strict budget compliance by stepping down lowest-ranked files if needed
        rendered_content, compressed_tokens, tree_tokens = self._render_within_strict_budget(
            root_path=resolved_root_str,
            files=files,
        )

        stats = self._build_compilation_stats(
            files=files,
            total_files_discovered=total_files_discovered,
            binary_files_skipped=binary_files_skipped,
            ignored_files_skipped=ignored_files_skipped,
            compressed_tokens=compressed_tokens,
            tree_overhead_tokens=tree_tokens,
            execution_time_ms=execution_time_ms,
        )

        return CompilationResult(
            root_path=resolved_root_str,
            output_format=self.config.output_format,
            content=rendered_content,
            stats=stats,
            files=files,
        )

    def _render_within_strict_budget(
        self,
        *,
        root_path: str,
        files: list[FileAnalysis],
    ) -> tuple[str, int, int]:
        """Render artifact and step down fidelity if wrapper tokens exceed `budget_tokens`."""
        budget = self.config.budget_tokens

        while True:
            tree_str = self.render_directory_tree(files, root_name=Path(root_path).name)
            tree_tokens = self.token_counter.count(tree_str)

            content = self._render_once(
                root_path=root_path,
                files=files,
                directory_tree=tree_str,
            )
            actual_tokens = self.token_counter.count(content)

            if actual_tokens <= budget:
                return content, actual_tokens, tree_tokens

            # Find lowest-ranked file currently above TREE_ONLY and step it down one tier
            active_files = [
                f for f in files if f.selected_fidelity > FidelityLevel.TREE_ONLY
            ]
            if not active_files:
                # Even with all files at TREE_ONLY, header + directory tree exceeds tiny budget;
                # compact the directory tree to guarantee budget compliance.
                compact_content = self._render_minimal_fallback(root_path, files, budget)
                compact_tokens = self.token_counter.count(compact_content)
                return compact_content, compact_tokens, min(tree_tokens, compact_tokens)

            lowest_file = min(
                active_files,
                key=lambda f: (f.pagerank_score, int(f.selected_fidelity)),
            )
            lowest_file.selected_fidelity = self._STEP_DOWN_MAP[lowest_file.selected_fidelity]

    def _render_once(
        self,
        *,
        root_path: str,
        files: list[FileAnalysis],
        directory_tree: str,
    ) -> str:
        fmt = self.config.output_format
        if fmt == OutputFormat.XML:
            return self._render_xml(root_path=root_path, files=files, directory_tree=directory_tree)
        if fmt == OutputFormat.JSON:
            return self._render_json(root_path=root_path, files=files, directory_tree=directory_tree)
        return self._render_markdown(root_path=root_path, files=files, directory_tree=directory_tree)

    def _render_markdown(
        self,
        *,
        root_path: str,
        files: list[FileAnalysis],
        directory_tree: str,
    ) -> str:
        repo_name = Path(root_path).name or "repository"
        raw_tokens = sum(f.raw_tokens for f in files)
        counts = self._count_fidelities(files)
        secrets_scrubbed = sum(f.redacted_secrets_count for f in files)

        sections: list[str] = [
            f"# Repository Context: `{repo_name}`",
            "",
            "## Executive Summary",
            f"- **Token Budget:** `{self.config.budget_tokens:,}` tokens | **Raw Repository Tokens:** `{raw_tokens:,}` tokens",
            f"- **Fidelity Allocation:** `FULL: {counts['FULL']}` | `SKEL: {counts['SKEL']}` | `SIGS: {counts['SIGS']}` | `TREE: {counts['TREE']}`",
        ]
        if self.config.focus_query:
            sections.append(f"- **Focus Query:** `{self.config.focus_query}`")
        if secrets_scrubbed > 0:
            sections.append(f"- **Secrets Redacted:** `{secrets_scrubbed}`")

        sections.extend(
            [
                "",
                "## Repository Directory Tree",
                "```text",
                directory_tree.rstrip(),
                "```",
            ]
        )

        # Emit file contents ordered by PageRank centrality descending
        ranked_files = sorted(
            [f for f in files if f.selected_fidelity > FidelityLevel.TREE_ONLY and f.selected_content.strip()],
            key=lambda f: (-f.pagerank_score, f.rel_path),
        )

        if ranked_files:
            sections.extend(["", "## Compiled Files (Ordered by Architectural Centrality)"])
            for file_obj in ranked_files:
                fid = file_obj.selected_fidelity
                pr_pct = file_obj.pagerank_score * 100.0
                lang_tag = file_obj.language if file_obj.language != "unknown" else "text"
                sections.extend(
                    [
                        "",
                        f"### `{file_obj.rel_path}` [{fid.badge}] (PageRank: {pr_pct:.1f}% | {file_obj.selected_tokens} tokens)",
                        f"```{lang_tag}",
                        file_obj.selected_content.rstrip(),
                        "```",
                    ]
                )

        return "\n".join(sections) + "\n"

    def _render_xml(
        self,
        *,
        root_path: str,
        files: list[FileAnalysis],
        directory_tree: str,
    ) -> str:
        repo_name = xml_escape(Path(root_path).name or "repository")
        raw_tokens = sum(f.raw_tokens for f in files)
        counts = self._count_fidelities(files)

        lines: list[str] = [
            f'<repository_context name="{repo_name}" budget_tokens="{self.config.budget_tokens}" raw_tokens="{raw_tokens}">',
            f'  <fidelity_summary full="{counts["FULL"]}" skel="{counts["SKEL"]}" sigs="{counts["SIGS"]}" tree="{counts["TREE"]}" />',
            "  <directory_tree><![CDATA[",
            directory_tree.rstrip(),
            "  ]]></directory_tree>",
            "  <files>",
        ]

        ranked_files = sorted(
            [f for f in files if f.selected_fidelity > FidelityLevel.TREE_ONLY and f.selected_content.strip()],
            key=lambda f: (-f.pagerank_score, f.rel_path),
        )

        for file_obj in ranked_files:
            escaped_path = xml_escape(file_obj.rel_path)
            escaped_lang = xml_escape(file_obj.language)
            badge = file_obj.selected_fidelity.badge
            pr_pct = f"{file_obj.pagerank_score * 100.0:.2f}%"
            safe_body = file_obj.selected_content.rstrip().replace("]]>", "]]]]><![CDATA[>")
            lines.extend(
                [
                    f'    <file path="{escaped_path}" language="{escaped_lang}" fidelity="{badge}" pagerank="{pr_pct}" tokens="{file_obj.selected_tokens}"><![CDATA[',
                    safe_body,
                    "    ]]></file>",
                ]
            )

        lines.extend(["  </files>", "</repository_context>\n"])
        return "\n".join(lines)

    def _render_json(
        self,
        *,
        root_path: str,
        files: list[FileAnalysis],
        directory_tree: str,
    ) -> str:
        ranked_files = sorted(
            files,
            key=lambda f: (-f.pagerank_score, f.rel_path),
        )
        payload: dict[str, Any] = {
            "repository": Path(root_path).name or "repository",
            "budget_tokens": self.config.budget_tokens,
            "focus_query": self.config.focus_query,
            "fidelity_summary": self._count_fidelities(files),
            "directory_tree": directory_tree.rstrip(),
            "files": [
                {
                    "path": f.rel_path,
                    "language": f.language,
                    "fidelity": f.selected_fidelity.badge,
                    "pagerank_score": round(f.pagerank_score, 6),
                    "tokens": f.selected_tokens,
                    "content": f.selected_content,
                }
                for f in ranked_files
                if f.selected_fidelity > FidelityLevel.TREE_ONLY
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    def _render_minimal_fallback(
        self,
        root_path: str,
        files: list[FileAnalysis],
        budget: int,
    ) -> str:
        """Produce a compact representation when `budget` is smaller than the full tree."""
        repo_name = Path(root_path).name or "repository"
        ranked = sorted(files, key=lambda f: -f.pagerank_score)

        if self.config.output_format == OutputFormat.XML:
            lines = [f'<repository_context name="{xml_escape(repo_name)}">']
            for f in ranked:
                candidate = "\n".join([*lines, f'  <file path="{xml_escape(f.rel_path)}" fidelity="TREE" />', "</repository_context>"])
                if self.token_counter.count(candidate) > budget:
                    break
                lines.append(f'  <file path="{xml_escape(f.rel_path)}" fidelity="TREE" />')
            lines.append("</repository_context>")
            return "\n".join(lines)

        if self.config.output_format == OutputFormat.JSON:
            kept_paths: list[str] = []
            for f in ranked:
                trial = json.dumps({"repository": repo_name, "files": [*kept_paths, f.rel_path]})
                if self.token_counter.count(trial) > budget:
                    break
                kept_paths.append(f.rel_path)
            return json.dumps({"repository": repo_name, "files": kept_paths})

        lines = [f"# `{repo_name}` (Budget: {budget} tokens)"]
        for f in ranked:
            entry = f"- `{f.rel_path}` [{f.selected_fidelity.badge}] (PR: {f.pagerank_score * 100:.1f}%)"
            trial = "\n".join([*lines, entry])
            if self.token_counter.count(trial) > budget:
                break
            lines.append(entry)
        return "\n".join(lines) + "\n"

    @classmethod
    def render_directory_tree(
        cls,
        files: list[FileAnalysis],
        root_name: str = ".",
    ) -> str:
        """Render an ASCII directory tree annotated with `[FULL|SKEL|SIGS|TREE]` badges."""
        if not files:
            return f"{root_name}/\n"

        tree_dict: dict[str, Any] = {}
        file_meta: dict[str, FileAnalysis] = {}

        for file_obj in sorted(files, key=lambda f: f.rel_path):
            file_meta[file_obj.rel_path] = file_obj
            parts = file_obj.rel_path.split("/")
            cursor = tree_dict
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = file_obj.rel_path

        lines: list[str] = [f"{root_name}/"]

        def _walk(node: dict[str, Any], prefix: str) -> None:
            entries = sorted(
                node.items(),
                key=lambda item: (not isinstance(item[1], dict), item[0]),
            )
            total = len(entries)
            for idx, (name, val) in enumerate(entries):
                is_last = idx == total - 1
                connector = "└── " if is_last else "├── "
                if isinstance(val, dict):
                    lines.append(f"{prefix}{connector}{name}/")
                    extension = "    " if is_last else "│   "
                    _walk(val, prefix + extension)
                else:
                    f_obj = file_meta[val]
                    badge = f_obj.selected_fidelity.badge
                    pr_pct = f_obj.pagerank_score * 100.0
                    lines.append(
                        f"{prefix}{connector}{name} [{badge}] (PR: {pr_pct:.1f}%)"
                    )

        _walk(tree_dict, "")
        return "\n".join(lines) + "\n"

    def _build_compilation_stats(
        self,
        *,
        files: list[FileAnalysis],
        total_files_discovered: int,
        binary_files_skipped: int,
        ignored_files_skipped: int,
        compressed_tokens: int,
        tree_overhead_tokens: int,
        execution_time_ms: float,
    ) -> CompilationStats:
        raw_tokens = sum(f.raw_tokens for f in files)
        budget = self.config.budget_tokens
        counts = self._count_fidelities(files)

        total_symbols = sum(len(f.symbols) for f in files)
        preserved_symbols = sum(
            len(f.symbols)
            for f in files
            if f.selected_fidelity >= FidelityLevel.SIGNATURES_ONLY
        )
        preserved_pct = (
            (preserved_symbols / total_symbols) * 100.0 if total_symbols > 0 else 100.0
        )

        compression_ratio = (
            round(raw_tokens / max(compressed_tokens, 1), 2) if raw_tokens > 0 else 1.0
        )
        savings_pct = (
            round((1.0 - (compressed_tokens / raw_tokens)) * 100.0, 2)
            if raw_tokens > 0
            else 0.0
        )
        utilization_pct = round((compressed_tokens / budget) * 100.0, 2)

        return CompilationStats(
            total_files_discovered=total_files_discovered,
            binary_files_skipped=binary_files_skipped,
            ignored_files_skipped=ignored_files_skipped,
            files_compiled=len(files),
            raw_tokens=raw_tokens,
            compressed_tokens=compressed_tokens,
            tree_overhead_tokens=tree_overhead_tokens,
            budget_tokens=budget,
            budget_utilization_pct=utilization_pct,
            compression_ratio=compression_ratio,
            token_savings_pct=savings_pct,
            fidelity_counts=counts,
            total_symbols_extracted=total_symbols,
            preserved_signatures_pct=round(preserved_pct, 2),
            secrets_redacted=sum(f.redacted_secrets_count for f in files),
            execution_time_ms=round(execution_time_ms, 2),
        )

    @staticmethod
    def _count_fidelities(files: list[FileAnalysis]) -> dict[str, int]:
        counts = {"FULL": 0, "SKEL": 0, "SIGS": 0, "TREE": 0}
        for file_obj in files:
            counts[file_obj.selected_fidelity.badge] += 1
        return counts
