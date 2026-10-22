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


class ArtifactFormatter:
    def __init__(
        self, config: CompilationConfig, token_counter: TokenCounterProtocol | None = None
    ) -> None:
        self.config = config
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
        root = Path(root_path).resolve()
        while True:
            tree = self.render_directory_tree(files, root.name)
            content = self._render(root.name, files, tree)
            if self.token_counter.count(content) <= self.config.budget_tokens:
                break
            active = [file for file in files if file.selected_fidelity > FidelityLevel.TREE]
            if not active:
                content = self._minimal(root.name, files)
                break
            lowest = min(active, key=lambda file: (file.pagerank_score, file.rel_path))
            lowest.selected_fidelity = FidelityLevel(int(lowest.selected_fidelity) - 1)

        count = self.token_counter.count(content)
        raw = sum(file.raw_tokens for file in files)
        counts = dict.fromkeys((level.badge for level in FidelityLevel), 0)
        counts.update(Counter(file.selected_fidelity.badge for file in files))
        symbols = sum(len(file.symbols) for file in files)
        preserved = 0
        for file in files:
            selected = " ".join(file.selected_content.split())
            if file.selected_fidelity != FidelityLevel.TREE:
                preserved += sum(
                    bool(signature) and signature in selected
                    for symbol in file.symbols
                    if (signature := " ".join(file.parsed.text(symbol.signature_range).split()))
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
            preserved_signatures_pct=preserved / symbols * 100 if symbols else 100.0,
            secrets_redacted=sum(file.redacted_secrets_count for file in files),
            execution_time_ms=execution_time_ms,
        )
        return CompilationResult(str(root), self.config.output_format, content, stats, files)

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
                f"### `{path}` [{file.selected_fidelity.badge}] (PageRank: {file.pagerank_score:.2%})",
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
        return "`" * max(
            3, max((len(match) + 1 for match in re.findall(r"`+", content)), default=0)
        )

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
