from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Protocol

import tiktoken

from contextcraft.ast import ParsedAst
from contextcraft.languages.base import Language


class FidelityLevel(IntEnum):
    TREE = 0
    SIGNATURES = 1
    SKELETON = 2
    FULL = 3

    @property
    def badge(self) -> str:
        return ("TREE", "SIGS", "SKEL", "FULL")[self]

    @property
    def semantic_utility(self) -> float:
        return (0.0, 0.45, 0.82, 1.0)[self]


@dataclass(frozen=True)
class RenderedTier:
    content: str
    tokens: int


class TokenCounter:
    """Count with tiktoken, using deterministic estimates if loading or encoding fails.

    Unknown encoding names raise ValueError rather than silently falling back.
    Offline estimates are not guaranteed to match the requested tokenizer.
    """

    _FALLBACK_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding_name = encoding_name
        self._encoder: tiktoken.Encoding | None
        try:
            self._encoder = tiktoken.get_encoding(encoding_name)
        except ValueError:
            raise
        except Exception:
            self._encoder = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text, disallowed_special=()))
            except Exception:
                pass
        lexical_pieces = len(self._FALLBACK_TOKEN_RE.findall(text))
        byte_estimate = max(1, len(text.encode("utf-8", errors="replace")) // 4)
        return max(lexical_pieces, byte_estimate)


class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...


class Elider:
    def __init__(self, token_counter: TokenCounterProtocol | None = None) -> None:
        self.token_counter: TokenCounterProtocol = (
            token_counter if token_counter is not None else TokenCounter()
        )

    def render(
        self,
        parsed: ParsedAst,
        language: type[Language],
    ) -> dict[FidelityLevel, RenderedTier]:
        """Build tiers with nondecreasing token costs from TREE through FULL.

        Empty or more expensive summaries reuse the next higher tier. FULL is
        the exact parsed source, which the caller should sanitize before parsing.
        """
        source = parsed.source.decode("utf-8")
        higher_tier = RenderedTier(source, self.token_counter.count(source))
        tiers = {
            FidelityLevel.TREE: RenderedTier("", 0),
            FidelityLevel.FULL: higher_tier,
        }

        for level, render in (
            (FidelityLevel.SKELETON, language.skeleton_builder(language.spec).build),
            (FidelityLevel.SIGNATURES, language.signatures_builder(language.spec).build),
        ):
            content = render(parsed)
            tier = RenderedTier(content, self.token_counter.count(content))
            if tier.tokens > higher_tier.tokens or not content.strip():
                tier = higher_tier
            tiers[level] = tier
            higher_tier = tier

        return {level: tiers[level] for level in FidelityLevel}
