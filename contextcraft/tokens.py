"""Count tokens with an optional fallback estimate."""

from __future__ import annotations

import re

import tiktoken

from contextcraft.config import TokenizerEncoding


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
