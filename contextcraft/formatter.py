from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from contextcraft.ast import ParsedAst
from contextcraft.elider import FidelityLevel, RenderedTier, TokenCounter, TokenCounterProtocol
from contextcraft.models import (
    CompilationConfig,
    CompilationResult,
    CompilationStats,
    FileAnalysis,
    InvalidBudgetError,
    OutputFormat,
)
from contextcraft.optimizer import TokenBudgetOptimizer
from contextcraft.utils import matches_path_patterns


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

        Selected fidelities may be lowered to fit format overhead; if pinned files
        have to be lowered, the other files are re-allocated around them. Signature
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

    _MAX_PIN_REFILLS = 3
    _MAX_PIN_RAISES = 48
    _MAX_REFILL_RENDERS = 8

    def _render_within_budget(self, name: str, files: list[FileAnalysis]) -> tuple[str, str]:
        """Return content and tree, minimizing utility lost per needed token.

        Each iteration recounts the entire artifact because wrapper and escaping
        costs differ by format. Tree-only output falls back to a minimal document.
        Pinned files give way only once every other file is down to TREE, in the
        reverse of the order the optimizer raised them. If that happens, their
        estimated cost was too low for this format, so the files are re-allocated
        under a budget scaled by the measured cost ratio, keeping whichever fitting
        allocation serves the pins better. Finally, pinned files are raised in
        measured steps to richer tiers that fit the real artifact, making room by
        trimming only unpinned files, and trimmed files take back leftover tokens.
        """
        optimizer = TokenBudgetOptimizer(self.config)
        pinned = {
            file.rel_path
            for file in files
            if matches_path_patterns(file.rel_path, self.config.pinned_full_files)
        }
        wrapper_tokens: int | None = None
        cost_ratio: float | None = None
        refills = 0
        finalized = False
        trimmed_from: dict[str, FidelityLevel] = {}
        # The best fitting state seen before a re-allocation, to be finished and compared.
        pending: tuple[tuple[tuple[int, ...], float], list[FidelityLevel]] | None = None
        best: tuple[tuple[tuple[int, ...], float], str, str, list[FidelityLevel]] | None = None
        while True:
            tree = self.render_budgeted_directory_tree(files, name)
            content = self._render(name, files, tree)
            overflow_tokens = self.token_counter.count(content) - self.config.budget_tokens
            if overflow_tokens <= 0:
                if cost_ratio is not None and refills < self._MAX_PIN_REFILLS:
                    # Re-allocate with pins first again, under a budget shrunk by how much
                    # this format's real cost exceeded the estimate.
                    refills += 1
                    key = self._pin_priority_key(files, pinned, optimizer)
                    if pending is None or key > pending[0]:
                        pending = (key, [file.selected_fidelity for file in files])
                    budget = max(1, int(self.config.budget_tokens / cost_ratio))
                    cost_ratio = None
                    TokenBudgetOptimizer(
                        self.config.model_copy(update={"budget_tokens": budget})
                    ).optimize(files, self._estimated_overhead(tree))
                    trimmed_from.clear()
                    continue
                if not finalized and (pinned or trimmed_from):
                    finalized = True
                    if wrapper_tokens is None:
                        wrapper_tokens = self._file_wrapper_tokens(name, tree)
                    used_tokens = overflow_tokens + self.config.budget_tokens
                    changed = False
                    if pinned:
                        changed, used_tokens = self._raise_pins(
                            name,
                            files,
                            pinned,
                            optimizer,
                            wrapper_tokens,
                            used_tokens,
                            trimmed_from,
                        )
                    if self._refill_trimmed(
                        name, files, trimmed_from, optimizer, wrapper_tokens, used_tokens
                    ):
                        changed = True
                    if changed:
                        continue
                key = self._pin_priority_key(files, pinned, optimizer)
                if pending is not None:
                    # A re-allocation can come out worse than the fitting state it replaced:
                    # finish that state the same way, then keep whichever serves pins better.
                    best = (key, content, tree, [file.selected_fidelity for file in files])
                    for file, level in zip(files, pending[1], strict=True):
                        file.selected_fidelity = level
                    pending = None
                    finalized = False
                    trimmed_from.clear()
                    continue
                if best is not None and best[0] > key:
                    for file, level in zip(files, best[3], strict=True):
                        file.selected_fidelity = level
                    return best[1], best[2]
                return content, tree

            active = [file for file in files if file.selected_fidelity > FidelityLevel.TREE]
            if not active:
                return self._minimal(name, files), tree
            if wrapper_tokens is None:
                wrapper_tokens = self._file_wrapper_tokens(name, tree)
            unpinned = [file for file in active if file.rel_path not in pinned]
            if not unpinned and cost_ratio is None:
                estimate = self._estimated_overhead(tree) + sum(
                    optimizer._effective_tier_cost(file, file.selected_fidelity) for file in active
                )
                cost_ratio = max(1.0, (overflow_tokens + self.config.budget_tokens) / estimate)
            steps = (
                self._utility_trim_order(unpinned, overflow_tokens, optimizer, wrapper_tokens)
                if unpinned
                else self._pin_trim_order(active, wrapper_tokens)
            )
            if not steps:
                return self._minimal(name, files), tree
            self._apply_trim(steps, overflow_tokens, pinned, trimmed_from)

    @staticmethod
    def _apply_trim(
        steps: list[tuple[FileAnalysis, FidelityLevel, int]],
        overflow_tokens: int,
        pinned: set[str],
        trimmed_from: dict[str, FidelityLevel],
    ) -> None:
        # Re-rendering after every downgrade makes large overflows quadratic, so apply
        # a prefix of the trim order while the estimated savings stay within half the
        # overflow. The margin absorbs estimates that undercount escaping by up to 2x;
        # a small overflow is still trimmed one downgrade at a time.
        saved = 0
        for index, (file, level, saved_tokens) in enumerate(steps):
            if index and 2 * (saved + saved_tokens) > overflow_tokens:
                break
            if file.rel_path not in pinned:
                trimmed_from.setdefault(file.rel_path, file.selected_fidelity)
            file.selected_fidelity = level
            saved += saved_tokens

    def _raise_pins(
        self,
        name: str,
        files: list[FileAnalysis],
        pinned: set[str],
        optimizer: TokenBudgetOptimizer,
        wrapper_tokens: int,
        used_tokens: int,
        trimmed_from: dict[str, FidelityLevel],
    ) -> tuple[bool, int]:
        """Raise pins tier by tier while the real artifact fits; report any change.

        Allocation works on estimates, so a pin can end a tier lower than the real
        output allows. Pins are raised in batches, rank order within each tier;
        each batch makes room by trimming unpinned files only and is undone if that
        is not enough. A failed single pin is skipped, and two in a row end the tier.
        """
        ranked = sorted(
            (file for file in files if file.rel_path in pinned),
            key=lambda item: (-item.pagerank_score, item.rel_path),
        )
        changed = False
        attempts = 0
        blocked: set[str] = set()
        for level in (FidelityLevel.SIGNATURES, FidelityLevel.SKELETON, FidelityLevel.FULL):
            single = False
            failures = 0
            while attempts < self._MAX_PIN_RAISES:
                room = self.config.budget_tokens - used_tokens
                room += sum(
                    file.selected_tokens + wrapper_tokens
                    for file in files
                    if file.selected_fidelity > FidelityLevel.TREE and file.rel_path not in pinned
                )
                batch: list[FileAnalysis] = []
                spent = 0
                for pin in ranked:
                    if pin.rel_path in blocked or pin.selected_fidelity >= level:
                        continue
                    extra = pin.tiers[level].tokens - pin.selected_tokens
                    if pin.selected_fidelity == FidelityLevel.TREE:
                        extra += wrapper_tokens
                    # Estimates are inexact (escaping, merged tokens), so near misses are
                    # measured rather than skipped.
                    if extra > room + wrapper_tokens:
                        blocked.add(pin.rel_path)
                        continue
                    if batch and (single or 2 * (spent + extra) > room):
                        break
                    batch.append(pin)
                    spent += extra
                if not batch:
                    break
                attempts += 1
                before = [(file, file.selected_fidelity) for file in files]
                trimmed_before = dict(trimmed_from)
                for pin in batch:
                    pin.selected_fidelity = level
                count = self._fit_by_trimming_unpinned(
                    name, files, pinned, optimizer, wrapper_tokens, trimmed_from
                )
                if count is not None:
                    used_tokens = count
                    changed = True
                    single = False
                    failures = 0
                    continue
                for file, fidelity in before:
                    file.selected_fidelity = fidelity
                trimmed_from.clear()
                trimmed_from.update(trimmed_before)
                if len(batch) == 1:
                    blocked.add(batch[0].rel_path)
                    failures += 1
                    if failures == 2:
                        break
                single = True
        return changed, used_tokens

    def _fit_by_trimming_unpinned(
        self,
        name: str,
        files: list[FileAnalysis],
        pinned: set[str],
        optimizer: TokenBudgetOptimizer,
        wrapper_tokens: int,
        trimmed_from: dict[str, FidelityLevel],
    ) -> int | None:
        """Trim unpinned files until the artifact fits; return its size, or None."""
        while True:
            tree = self.render_budgeted_directory_tree(files, name)
            count = self.token_counter.count(self._render(name, files, tree))
            overflow_tokens = count - self.config.budget_tokens
            if overflow_tokens <= 0:
                return count
            unpinned = [
                file
                for file in files
                if file.selected_fidelity > FidelityLevel.TREE and file.rel_path not in pinned
            ]
            steps = self._utility_trim_order(unpinned, overflow_tokens, optimizer, wrapper_tokens)
            if not steps:
                return None
            self._apply_trim(steps, overflow_tokens, pinned, trimmed_from)

    def _refill_trimmed(
        self,
        name: str,
        files: list[FileAnalysis],
        trimmed_from: dict[str, FidelityLevel],
        optimizer: TokenBudgetOptimizer,
        wrapper_tokens: int,
        used_tokens: int,
    ) -> bool:
        """Give leftover tokens back to trimmed files, best utility per token first.

        Whole-file tiers make the last trim overshoot, sometimes by hundreds of
        tokens. Each batch is checked against the real artifact and undone if it
        overflows; a failed single step stops that file, and two in a row (when
        escaping makes every estimate too low) stop the pass.
        """
        by_path = {file.rel_path: file for file in files}
        open_paths = dict(trimmed_from)
        changed = False
        single = False
        failures = 0
        for _ in range(self._MAX_REFILL_RENDERS):
            slack = self.config.budget_tokens - used_tokens
            candidates: list[tuple[float, str, FidelityLevel, int]] = []
            for path, ceiling in open_paths.items():
                file = by_path[path]
                if file.selected_fidelity >= ceiling:
                    continue
                level = FidelityLevel(file.selected_fidelity + 1)
                cost = file.tiers[level].tokens - file.selected_tokens
                if file.selected_fidelity == FidelityLevel.TREE:
                    cost += wrapper_tokens
                if cost > slack:
                    continue
                gain = optimizer.tier_utility(file, level) - optimizer.tier_utility(
                    file, file.selected_fidelity
                )
                candidates.append((-gain / max(cost, 1), path, level, max(cost, 0)))
            if not candidates:
                return changed
            candidates.sort()
            batch: list[tuple[FileAnalysis, FidelityLevel]] = []
            spent = 0
            for _, path, level, cost in candidates:
                if batch and (single or 2 * (spent + cost) > slack):
                    break
                file = by_path[path]
                batch.append((file, file.selected_fidelity))
                file.selected_fidelity = level
                spent += cost
            tree = self.render_budgeted_directory_tree(files, name)
            count = self.token_counter.count(self._render(name, files, tree))
            if count <= self.config.budget_tokens:
                used_tokens = count
                changed = True
                single = False
                failures = 0
                continue
            for file, fidelity in batch:
                file.selected_fidelity = fidelity
            if len(batch) == 1:
                del open_paths[batch[0][0].rel_path]
                failures += 1
                if failures == 2:
                    return changed
            single = True
        return changed

    @staticmethod
    def _pin_priority_key(
        files: list[FileAnalysis], pinned: set[str], optimizer: TokenBudgetOptimizer
    ) -> tuple[tuple[int, ...], float]:
        """Order allocations by pins kept at each tier, then by total utility."""
        pins = [file.selected_fidelity for file in files if file.rel_path in pinned]
        coverage = tuple(sum(level >= tier for level in pins) for tier in list(FidelityLevel)[1:])
        utility = sum(optimizer.tier_utility(file, file.selected_fidelity) for file in files)
        return coverage, utility

    def _estimated_overhead(self, tree: str) -> int:
        return TokenBudgetOptimizer.BASE_DOCUMENT_OVERHEAD_TOKENS + self.token_counter.count(tree)

    @staticmethod
    def _utility_trim_order(
        files: list[FileAnalysis],
        overflow_tokens: int,
        optimizer: TokenBudgetOptimizer,
        wrapper_tokens: int,
    ) -> list[tuple[FileAnalysis, FidelityLevel, int]]:
        """Downgrades by utility lost per token, up to the first file seen twice.

        A file's next step depends on the tier its first step leaves it at, so the
        order is only known up to that point.
        """
        candidates: list[tuple[float, str, FidelityLevel, FileAnalysis, int]] = []
        for file in files:
            current_value = optimizer.tier_utility(file, file.selected_fidelity)
            for level in FidelityLevel:
                if level >= file.selected_fidelity:
                    continue
                saved_tokens = file.selected_tokens - file.tiers[level].tokens
                if level == FidelityLevel.TREE:
                    saved_tokens += wrapper_tokens
                if saved_tokens <= 0:
                    continue
                loss = current_value - optimizer.tier_utility(file, level)
                candidates.append(
                    (
                        loss / min(saved_tokens, overflow_tokens),
                        file.rel_path,
                        level,
                        file,
                        saved_tokens,
                    )
                )
        candidates.sort(key=lambda item: item[:3])
        order: list[tuple[FileAnalysis, FidelityLevel, int]] = []
        seen: set[str] = set()
        for _, path, level, file, saved_tokens in candidates:
            if path in seen:
                break
            seen.add(path)
            order.append((file, level, saved_tokens))
        return order

    @staticmethod
    def _pin_trim_order(
        pinned: list[FileAnalysis], wrapper_tokens: int
    ) -> list[tuple[FileAnalysis, FidelityLevel, int]]:
        """Undo the optimizer's pin allocation: FULL steps first, lowest PageRank first."""
        ranked = sorted(pinned, key=lambda item: (item.pagerank_score, item.rel_path))
        tiers = {file.rel_path: file.selected_fidelity for file in ranked}
        order: list[tuple[FileAnalysis, FidelityLevel, int]] = []
        for level in (FidelityLevel.SKELETON, FidelityLevel.SIGNATURES, FidelityLevel.TREE):
            for file in ranked:
                current = tiers[file.rel_path]
                if current <= level:
                    continue
                tiers[file.rel_path] = level
                saved_tokens = file.tiers[current].tokens - file.tiers[level].tokens
                if level == FidelityLevel.TREE:
                    saved_tokens += wrapper_tokens
                if saved_tokens > 0:
                    order.append((file, level, saved_tokens))
        return order

    def _file_wrapper_tokens(self, name: str, tree: str) -> int:
        """Measure what one more file's entry costs in this format beyond its content."""
        content = "x"

        def sample(path: str) -> FileAnalysis:
            return FileAnalysis(
                rel_path=path,
                abs_path="",
                language="python",
                size_bytes=len(content),
                parsed=ParsedAst(source=content.encode()),
                tiers={level: RenderedTier(content, 1) for level in FidelityLevel},
                pagerank_score=0.012345678901234567,
                selected_fidelity=FidelityLevel.FULL,
            )

        first, second = sample("src/package/module.py"), sample("src/package/other.py")
        one = self.token_counter.count(self._render(name, [first], tree))
        two = self.token_counter.count(self._render(name, [first, second], tree))
        return max(two - one - 1, 1)

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
