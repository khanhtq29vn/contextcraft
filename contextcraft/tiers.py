"""Render file representations and count content and framed tokens."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

from contextcraft.config import Config
from contextcraft.formatter import ArtifactFormatter
from contextcraft.models import FidelityLevel, Index, RenderedTier, Source, Tiers
from contextcraft.tokens import TokenCounter


class TierRenderer:
    """Render file tiers with the language implementations recorded in the index."""

    def render(self, index: Index, source: Source, config: Config) -> Tiers:
        """Render available file tiers and count content and framed tokens.

        Args:
            index: Files to render and their detected languages.
            source: Loaded bytes keyed by index file ID.
            config: Output format, tokenizer encoding, estimate policy, and workers.

        Returns:
            A TREE tier for every file, plus FULL, SKEL, and SIGS tiers for
            files with loaded source. Files with no detected language reuse
            full source. If a compressed rendering is empty or larger than
            the next richer tier, it reuses that tier's content instead. Higher
            fidelity therefore never has a lower content token count. Framed
            costs are counted separately for each tier's label and output format.

        Raises:
            ValueError: If the worker count is not positive.
            KeyError: If a loaded file's language or analysis is missing.
        """
        if config.workers <= 0:
            raise ValueError("Worker count must be positive")

        counter = TokenCounter(
            config.tokenizer_encoding,
            allow_estimates=config.allow_token_estimates,
        )

        formatter = ArtifactFormatter()
        tree = RenderedTier(content="", tokens=0, framed_tokens=0)
        tiers = {}
        estimated = False

        def render_file(
            file_id: int,
        ) -> tuple[dict[FidelityLevel, RenderedTier], bool]:
            file = index.files[file_id]
            file_tiers = {FidelityLevel.TREE: tree}
            source_bytes = source.content.get(file_id)

            if source_bytes is None:
                return file_tiers, False

            file_counter = (
                TokenCounter(
                    config.tokenizer_encoding,
                    allow_estimates=config.allow_token_estimates,
                )
                if config.workers > 1
                else counter
            )
            path = file.path.relative_to(index.path).as_posix()
            content = source_bytes.decode("utf-8")
            higher = RenderedTier(
                content=content,
                tokens=file_counter.count(content),
                framed_tokens=formatter.file_cost(
                    path, content, FidelityLevel.FULL, file_counter, config
                ),
            )
            file_tiers[FidelityLevel.FULL] = higher
            language = (
                index.languages[file.language_id]
                if file.language_id is not None
                else None
            )

            for level in (FidelityLevel.SKEL, FidelityLevel.SIGS):
                tier_content = higher.content
                tier_tokens = higher.tokens

                if language is not None:
                    analysis = source.analyses[file_id]
                    content = (
                        language.render_skel(source_bytes, analysis)
                        if level == FidelityLevel.SKEL
                        else language.render_sigs(source_bytes, analysis)
                    )

                    tokens = file_counter.count(content)

                    if content.strip() and tokens <= higher.tokens:
                        tier_content = content
                        tier_tokens = tokens

                tier = RenderedTier(
                    content=tier_content,
                    tokens=tier_tokens,
                    framed_tokens=formatter.file_cost(
                        path, tier_content, level, file_counter, config
                    ),
                )
                file_tiers[level] = tier
                higher = tier

            return (
                {level: file_tiers[level] for level in FidelityLevel},
                file_counter.used_estimates,
            )

        file_ids = sorted(index.files)

        with (
            ThreadPoolExecutor(max_workers=config.workers)
            if config.workers > 1
            else nullcontext()
        ) as executor:
            results = (
                executor.map(render_file, file_ids)
                if executor is not None
                else map(render_file, file_ids)
            )

            for file_id, (file_tiers, file_estimated) in zip(file_ids, results):
                tiers[file_id] = file_tiers
                estimated |= file_estimated

        return Tiers(
            output_format=config.output_format,
            tokenizer_encoding=config.tokenizer_encoding,
            files=tiers,
            token_counts_estimated=estimated,
        )
