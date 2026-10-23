from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from contextcraft.elider import FidelityLevel, TokenCounter, TokenCounterProtocol
from contextcraft.models import (
    CompilationConfig,
    CompilationResult,
    CompilationStats,
    FileAnalysis,
    InvalidBudgetError,
    OutputFormat,
)
from contextcraft.optimizer import TokenBudgetOptimizer


class ArtifactFormatter:
    """Render selected tiers and verify the complete artifact's token budget."""

    def __init__(
        self,
        config: CompilationConfig,
        token_counter: TokenCounterProtocol | None = None,
    ) -> None:
        self.config = config
        self._compact_tree_key: tuple[str, int, tuple[tuple[str, float], ...]] | None = None
        self._compact_tree = ""
        self.token_counter = (
            token_counter if token_counter is not None else TokenCounter(config.tokenizer_encoding)
        )

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
        """Render an artifact and compute statistics from its final allocation.

        Selected fidelities may be lowered to fit format overhead. Signature
        coverage is estimated from final tiers, not measured by reparsing output.
        """
        root = Path(root_path).resolve()
        content, tree = self._render_within_budget(root.name, files)
        count = self.token_counter.count(content)
        raw = sum(file.raw_tokens for file in files)
        counts = dict.fromkeys((level.badge for level in FidelityLevel), 0)
        counts.update(Counter(file.selected_fidelity.badge for file in files))
        symbols = sum(len(file.symbols) for file in files)
        public_signatures = sum(symbol.is_public for file in files for symbol in file.symbols)
        preserved = sum(
            symbol.is_public
            for file in files
            if file.selected_fidelity >= FidelityLevel.SIGNATURES
            for symbol in file.symbols
        )
        stats = CompilationStats(
            total_files_discovered=total_files_discovered,
            binary_files_skipped=binary_files_skipped,
            ignored_files_skipped=ignored_files_skipped,
            files_compiled=len(files),
            raw_tokens=raw,
            compressed_tokens=count,
            tree_overhead_tokens=min(count, self.token_counter.count(tree)),
            budget_tokens=self.config.budget_tokens,
            budget_utilization_pct=round(count / self.config.budget_tokens * 100, 2),
            compression_ratio=round(raw / max(count, 1), 2) if raw else 1.0,
            token_savings_pct=round((1 - count / raw) * 100, 2) if raw else 0.0,
            fidelity_counts=counts,
            total_symbols_extracted=symbols,
            total_public_signatures=public_signatures,
            preserved_public_signatures=preserved,
            preserved_signatures_pct=preserved / public_signatures * 100
            if public_signatures
            else 100.0,
            secrets_redacted=sum(file.redacted_secrets_count for file in files),
            execution_time_ms=execution_time_ms,
        )
        return CompilationResult(str(root), self.config.output_format, content, stats, files)

    def _render_within_budget(self, name: str, files: list[FileAnalysis]) -> tuple[str, str]:
        """Return content and tree, minimizing utility lost per needed token.

        Each iteration recounts the entire artifact because wrapper and escaping
        costs differ by format. Tree-only output falls back to a minimal document.
        """
        optimizer = TokenBudgetOptimizer(self.config)
        while True:
            tree = self.render_budgeted_directory_tree(files, name)
            content = self._render(name, files, tree)
            overflow_tokens = self.token_counter.count(content) - self.config.budget_tokens
            if overflow_tokens <= 0:
                return content, tree

            active = [file for file in files if file.selected_fidelity > FidelityLevel.TREE]
            if not active:
                return self._minimal(name, files), tree

            downgrades: list[tuple[float, str, FidelityLevel, FileAnalysis]] = []
            for file in active:
                current_value = optimizer.tier_utility(file, file.selected_fidelity)
                for level in FidelityLevel:
                    if level >= file.selected_fidelity:
                        continue
                    saved_tokens = file.selected_tokens - file.tiers[level].tokens
                    if level == FidelityLevel.TREE:
                        saved_tokens += TokenBudgetOptimizer.FILE_WRAPPER_OVERHEAD_TOKENS
                    if saved_tokens <= 0:
                        continue
                    loss = current_value - optimizer.tier_utility(file, level)
                    downgrades.append(
                        (
                            loss / min(saved_tokens, overflow_tokens),
                            file.rel_path,
                            level,
                            file,
                        )
                    )
            _, _, level, file = min(downgrades, key=lambda item: item[:3])
            file.selected_fidelity = level

    def _render(self, name: str, files: list[FileAnalysis], tree: str) -> str:
        ranked = sorted(files, key=lambda file: (-file.pagerank_score, file.rel_path))
        active = [
            file
            for file in ranked
            if file.selected_fidelity > FidelityLevel.TREE and file.selected_content.strip()
        ]
        counts = Counter(file.selected_fidelity.badge for file in files)
        if self.config.output_format == OutputFormat.JSON:
            return (
                json.dumps(
                    {
                        "repository": name,
                        "budget_tokens": self.config.budget_tokens,
                        "focus_query": self.config.focus_query,
                        "fidelity_summary": {
                            level.badge: counts[level.badge] for level in FidelityLevel
                        },
                        "directory_tree": tree,
                        "files": [
                            {
                                "path": file.rel_path,
                                "language": file.language,
                                "fidelity": file.selected_fidelity.badge,
                                "pagerank_score": file.pagerank_score,
                                "tokens": file.selected_tokens,
                                "content": file.selected_content,
                            }
                            for file in active
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
        if self.config.output_format == OutputFormat.XML:
            root = ET.Element(
                "repository_context",
                name=self._xml_safe(name),
                budget_tokens=str(self.config.budget_tokens),
            )
            ET.SubElement(root, "directory_tree").text = self._xml_safe(tree)
            children = ET.SubElement(root, "files")
            for file in active:
                element = ET.SubElement(
                    children,
                    "file",
                    {
                        "path": self._xml_safe(file.rel_path),
                        "language": self._xml_safe(file.language),
                        "fidelity": file.selected_fidelity.badge,
                        "pagerank": str(file.pagerank_score),
                        "tokens": str(file.selected_tokens),
                    },
                )
                element.text = self._xml_safe(file.selected_content)
            return ET.tostring(root, encoding="unicode") + "\n"

        lines = [
            f"# Repository Context: `{name}`",
            "",
            "## Executive Summary",
            f"- Token Budget: {self.config.budget_tokens}",
            f"- Raw Repository Tokens: {sum(file.raw_tokens for file in files)}",
            "- Fidelity Allocation: "
            + " | ".join(f"{level.badge}: {counts[level.badge]}" for level in FidelityLevel),
        ]
        if self.config.focus_query:
            lines.append(f"- Focus Query: {self.config.focus_query}")
        lines += [
            "",
            "## Repository Directory Tree",
            self._fence(tree),
            tree.rstrip(),
            self._fence(tree),
        ]
        if active:
            lines += ["", "## Compiled Files (Ordered by Architectural Centrality)"]
        for file in active:
            fence = self._fence(file.selected_content)
            path = file.rel_path.replace("\n", "\\n").replace("`", "\\`")
            lines += [
                "",
                f"### `{path}` [{file.selected_fidelity.badge}]",
                fence + file.language,
                file.selected_content.rstrip("\n"),
                fence,
            ]
        return "\n".join(lines) + "\n"

    def _minimal(self, name: str, files: list[FileAnalysis]) -> str:
        budget = self.config.budget_tokens
        ranked = sorted(files, key=lambda file: (-file.pagerank_score, file.rel_path))
        if self.config.output_format == OutputFormat.JSON:
            payload: dict[str, Any] = {"repository": name, "files": []}
            content = json.dumps(payload, ensure_ascii=False)
            if self.token_counter.count(content) > budget:
                for minimal in ("{}", "null", "0"):
                    if self.token_counter.count(minimal) <= budget:
                        return minimal
                raise InvalidBudgetError("Budget too small for valid JSON")
            paths: list[str] = []
            for file in ranked:
                trial = json.dumps(
                    {"repository": name, "files": [*paths, file.rel_path]}, ensure_ascii=False
                )
                if self.token_counter.count(trial) <= budget:
                    paths.append(file.rel_path)
                    content = trial
            return content
        if self.config.output_format == OutputFormat.XML:
            root = ET.Element("repository_context")
            content = ET.tostring(root, encoding="unicode")
            if self.token_counter.count(content) > budget:
                raise InvalidBudgetError("Budget too small for valid XML")
            for file in ranked:
                child = ET.SubElement(
                    root, "file", path=self._xml_safe(file.rel_path), fidelity="TREE"
                )
                trial = ET.tostring(root, encoding="unicode")
                if self.token_counter.count(trial) > budget:
                    root.remove(child)
                else:
                    content = trial
            return content
        content = f"# `{name}`\n"
        if self.token_counter.count(content) > budget:
            content = ""
        for file in ranked:
            trial = content + f"- {json.dumps(file.rel_path, ensure_ascii=False)} [TREE]\n"
            if self.token_counter.count(trial) <= budget:
                content = trial
        return content

    @staticmethod
    def _xml_safe(content: str) -> str:
        return re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]",
            lambda match: f"\\u{ord(match[0]):04x}",
            content,
        )

    @staticmethod
    def _fence(content: str) -> str:
        """Choose a Markdown fence longer than any backtick run in the content."""
        longest_run = max((len(run) for run in re.findall(r"`+", content)), default=0)
        return "`" * max(3, longest_run + 1)

    def render_budgeted_directory_tree(
        self, files: list[FileAnalysis], root_name: str = "."
    ) -> str:
        """Use at most 10% of the budget, favoring ranked paths if the tree is too large."""
        max_tokens = self.config.budget_tokens // 10
        tree = self.render_directory_tree(files, root_name)
        if self.token_counter.count(tree) <= max_tokens:
            return tree

        key = (root_name, max_tokens, tuple((file.rel_path, file.pagerank_score) for file in files))
        if key == self._compact_tree_key:
            return self._compact_tree

        header = json.dumps(root_name, ensure_ascii=False) + "/\n"
        lines: list[str] = []

        def compact_tree(paths: list[str]) -> str:
            omitted = len(files) - len(paths)
            suffix = f"... {omitted} files omitted\n" if omitted else ""
            return header + "".join(paths) + suffix

        tree = compact_tree(lines)
        if self.token_counter.count(tree) > max_tokens:
            return ""
        for file in sorted(files, key=lambda item: (-item.pagerank_score, item.rel_path)):
            line = "- " + json.dumps(file.rel_path, ensure_ascii=False) + "\n"
            candidate = compact_tree([*lines, line])
            if self.token_counter.count(candidate) <= max_tokens:
                lines.append(line)
                tree = candidate
        self._compact_tree_key = key
        self._compact_tree = tree
        return tree

    @staticmethod
    def render_directory_tree(files: list[FileAnalysis], root_name: str = ".") -> str:
        tree: dict[str, Any] = {}
        for file in sorted(files, key=lambda item: item.rel_path):
            cursor = tree
            parts = file.rel_path.split("/")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = file
        lines = [root_name + "/"]

        def walk(node: dict[str, Any], prefix: str) -> None:
            items = sorted(node.items(), key=lambda item: (not isinstance(item[1], dict), item[0]))
            for index, (name, value) in enumerate(items):
                last = index == len(items) - 1
                connector = "└── " if last else "├── "
                safe_name = name.replace("\n", "\\n")
                if isinstance(value, dict):
                    lines.append(prefix + connector + safe_name + "/")
                    walk(value, prefix + ("    " if last else "│   "))
                else:
                    lines.append(
                        f"{prefix}{connector}{safe_name} [{value.selected_fidelity.badge}] (PR: {value.pagerank_score:.1%})"
                    )

        walk(tree, "")
        return "\n".join(lines) + "\n"
