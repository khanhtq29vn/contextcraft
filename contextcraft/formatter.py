"""Serialize selected file tiers and enforce the final output budget."""

from __future__ import annotations

import json
import re
from xml.etree import ElementTree as ET

from contextcraft.config import Config, OutputFormat
from contextcraft.models import Artifact, FidelityLevel, Index, Selection, Tiers
from contextcraft.tiers import TokenCounter


class ArtifactFormatter:
    """Format repository context as Markdown, XML, or JSON."""

    def _render_file(
        self,
        index: Index,
        tiers: Tiers,
        file_id: int,
        level: FidelityLevel,
        config: Config,
    ) -> str:
        file = index.files[file_id]
        path = file.path.relative_to(index.path).as_posix()
        content = tiers.files[file_id][level].content

        if config.output_format == OutputFormat.JSON:
            return json.dumps(
                {"path": path, "tier": level.name, "content": content},
                ensure_ascii=False,
                separators=(",", ":"),
            )

        if config.output_format == OutputFormat.XML:
            element = ET.Element("file", path=path, tier=level.name)
            element.text = content

            return ET.tostring(element, encoding="unicode")

        fence = "`" * max(
            3, max((len(run) + 1 for run in re.findall(r"`+", content)), default=3)
        )

        return f"## {json.dumps(path, ensure_ascii=False)} [{level.name}]\n\n{fence}\n{content}\n{fence}\n\n"

    def file_cost(
        self,
        index: Index,
        tiers: Tiers,
        file_id: int,
        level: FidelityLevel,
        counter: TokenCounter,
        config: Config,
    ) -> int:
        """Return a file's token cost at the requested tier, including framing.

        TREE costs zero because paths have a separate budget. JSON costs include
        a trailing comma. Use the same counter and config as for the final output,
        but note that joining blocks may change how they tokenize.
        """
        if level == FidelityLevel.TREE:
            return 0

        block = self._render_file(index, tiers, file_id, level, config)

        return counter.count(
            block + ("," if config.output_format == OutputFormat.JSON else "")
        )

    def render(
        self,
        index: Index,
        tiers: Tiers,
        selections: dict[int, FidelityLevel],
        tree: tuple[str, ...],
        config: Config,
    ) -> str:
        """Serialize selected tiers and a caller-supplied path listing.

        Args:
            index: File metadata and repository root for relative paths.
            tiers: Content available at each selected tier.
            selections: File IDs and fidelity levels to emit. TREE emits no block.
            tree: Relative paths to list, normally from directory_tree.
            config: Output format to use.

        Returns:
            Serialized context without token-budget validation. Paths not
            listed in tree are counted in the omitted-path total.
        """
        blocks = [
            self._render_file(index, tiers, file_id, level, config)
            for file_id, level in sorted(selections.items())
            if level != FidelityLevel.TREE
        ]

        omitted = len(index.files) - len(tree)

        if config.output_format == OutputFormat.JSON:
            header = json.dumps(
                {"tree": tree, "omitted_paths": omitted},
                ensure_ascii=False,
                separators=(",", ":"),
            )

            return header[:-1] + ',"files":[' + ",".join(blocks) + "]}"

        if config.output_format == OutputFormat.XML:
            element = ET.Element("tree", omitted_paths=str(omitted))

            for path in tree:
                ET.SubElement(element, "file", path=path)

            return (
                "<repository_context>"
                + ET.tostring(element, encoding="unicode")
                + "<files>"
                + "".join(blocks)
                + "</files></repository_context>"
            )

        listing = "".join(
            f"- {json.dumps(path, ensure_ascii=False)}\n" for path in tree
        )

        if omitted:
            listing += f"- {omitted} paths omitted\n"

        return (
            "# Repository context\n\n"
            + listing
            + ("\n" if listing else "")
            + "".join(blocks)
        )

    def directory_tree(
        self, index: Index, tiers: Tiers, counter: TokenCounter, config: Config
    ) -> tuple[str, ...]:
        """List relative paths in file-ID order until the tree budget is reached.

        The listing uses at most one tenth of config.budget_tokens beyond the
        cost of empty output framing, as measured by the supplied counter and
        format. Use tiers from the same index. The listing contains no file content.
        """
        paths = tuple(
            file.path.relative_to(index.path).as_posix()
            for _, file in sorted(index.files.items())
        )

        baseline = counter.count(self.render(index, tiers, {}, (), config))
        limit = config.budget_tokens // 10
        low, high = 0, len(paths)

        while low < high:
            middle = (low + high + 1) // 2
            cost = (
                counter.count(self.render(index, tiers, {}, paths[:middle], config))
                - baseline
            )

            if cost <= limit:
                low = middle
            else:
                high = middle - 1

        return paths[:low]

    def format(
        self,
        index: Index,
        tiers: Tiers,
        scores: dict[int, float],
        selection: Selection,
        config: Config,
    ) -> Artifact:
        """Format selected tiers, lowering fidelity as needed to fit the budget.

        Args:
            index: Repository files to include in the allocation.
            tiers: Available content for each indexed file.
            scores: File weights used to choose downgrades with less utility loss.
            selection: Initial tier for every indexed file; left unchanged.
            config: Output format, token budget, and tokenizer options.

        Returns:
            An artifact with the final content, token count, and selected tiers.
            To fit the budget, the formatter may lower file tiers or shorten the
            path listing. Counts are exact unless token_counts_estimated is true.

        Raises:
            ValueError: If selection does not cover exactly the indexed files,
                or even empty output framing exceeds the budget.
        """
        if set(selection.tiers) != set(index.files):
            raise ValueError("Allocate file tiers before formatting")

        counter = TokenCounter(
            config.tokenizer_encoding,
            allow_estimates=config.allow_token_estimates,
        )

        selections = dict(selection.tiers)
        tree = self.directory_tree(index, tiers, counter, config)
        costs = {
            file_id: {
                level: self.file_cost(index, tiers, file_id, level, counter, config)
                for level in tiers.files[file_id]
            }
            for file_id in index.files
        }

        while True:
            content = self.render(index, tiers, selections, tree, config)
            tokens = counter.count(content)

            if tokens <= config.budget_tokens:
                break

            downgrades = []

            for file_id, current in selections.items():
                for level in tiers.files[file_id]:
                    savings = costs[file_id][current] - costs[file_id][level]

                    if level < current and savings > 0:
                        loss = scores[file_id] * (
                            current.semantic_utility - level.semantic_utility
                        )

                        downgrades.append((loss / savings, loss, file_id, level))

            if downgrades:
                _, _, file_id, level = min(downgrades)
                selections[file_id] = level
            elif tree:
                tree = tree[: len(tree) // 2]
            else:
                raise ValueError("Token budget is too small for the output framing")

        estimated = (
            tiers.token_counts_estimated
            or selection.token_counts_estimated
            or counter.used_estimates
        )

        return Artifact(
            content=content,
            tokens=tokens,
            token_counts_estimated=estimated,
            selected_tiers=selections,
        )
