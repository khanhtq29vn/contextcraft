"""Count tokens and render file representations at each fidelity level."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

import tiktoken

from contextcraft.config import Config, TokenizerEncoding
from contextcraft.models import FidelityLevel, Index, RenderedTier, Source, Tiers


class TokenCounter:
    """Count tokens with an optional fallback estimate.

    Args:
        encoding: Tiktoken encoding to use. Loading it may download encoding data.
        allow_estimates: Fall back to an estimate if loading or encoding fails.
            An invalid encoding name still raises ValueError.

    Attributes:
        used_estimates: True once any count on this instance uses an estimate;
            subsequent calls do not reset it.
    """

    def __init__(
        self,
        encoding: TokenizerEncoding,
        *,
        allow_estimates: bool = True,
    ) -> None:
        self.allow_estimates = allow_estimates
        self.used_estimates = False
        self.encoder: tiktoken.Encoding | None

        try:
            self.encoder = tiktoken.get_encoding(encoding.value)
        except ValueError:
            raise
        except Exception:
            if not allow_estimates:
                raise

            self.encoder = None

    def count(self, content: str) -> int:
        """Return the token count for content, or zero for empty content.

        Special-token text is counted as ordinary text. Encoding errors
        propagate unless estimates are enabled. An estimate sets used_estimates
        and cannot guarantee that the output fits a strict token budget.
        """
        if not content:
            return 0

        if self.encoder is not None:
            try:
                return len(self.encoder.encode(content, disallowed_special=()))
            except Exception:
                if not self.allow_estimates:
                    raise

        self.used_estimates = True
        pieces = len(re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", content))
        byte_estimate = max(1, len(content.encode("utf-8")) // 4)

        return max(pieces, byte_estimate)


class TierRenderer:
    """Render file tiers with the language implementations recorded in the index."""

    def render(self, index: Index, source: Source, config: Config) -> Tiers:
        """Render available file tiers and count tokens without output framing.

        Args:
            index: Files to render and their detected languages.
            source: Loaded bytes keyed by index file ID.
            config: Tokenizer encoding, estimate policy, and worker count.

        Returns:
            A TREE tier for every file, plus FULL, SKEL, and SIGS tiers for
            files with loaded source. Files with no detected language reuse
            full source. If a compressed rendering is empty or larger than
            the next richer tier, it reuses that tier instead. Higher fidelity
            therefore never has a lower content token count.

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

        tree = RenderedTier(content="", tokens=0)
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
            content = source_bytes.decode("utf-8")
            higher = RenderedTier(content=content, tokens=file_counter.count(content))
            file_tiers[FidelityLevel.FULL] = higher
            language = (
                index.languages[file.language_id]
                if file.language_id is not None
                else None
            )

            for level in (FidelityLevel.SKEL, FidelityLevel.SIGS):
                tier = higher

                if language is not None:
                    analysis = source.analyses[file_id]
                    content = (
                        language.render_skel(source_bytes, analysis)
                        if level == FidelityLevel.SKEL
                        else language.render_sigs(source_bytes, analysis)
                    )

                    tokens = file_counter.count(content)

                    if content.strip() and tokens <= higher.tokens:
                        tier = RenderedTier(content=content, tokens=tokens)

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

        return Tiers(files=tiers, token_counts_estimated=estimated)
