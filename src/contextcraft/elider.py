"""Multi-resolution AST elision engine and offline-resilient token counter.

For every `FileAnalysis` in the repository, `MultiResolutionElider` pre-computes
4 discrete fidelity representations:
- `FidelityLevel.FULL_SOURCE (3)`: Complete sanitized source code.
- `FidelityLevel.SKELETON_WITH_DOCSTRINGS (2)`: Surgical AST body elision that
  replaces function/method implementation bodies in reverse byte-offset order
  while preserving 100% of imports, class declarations, type annotations,
  function signatures, and docstrings.
- `FidelityLevel.SIGNATURES_ONLY (1)`: Compact architectural summary of imports
  and exported class/function signatures without docstrings or comments.
- `FidelityLevel.TREE_ONLY (0)`: Empty body (listed in the directory tree only).
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from contextcraft.languages import get_extractor
from contextcraft.models import ByteRange, FidelityLevel, FileAnalysis, SymbolNode

try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore[assignment]
    HAS_TIKTOKEN = False


class TokenCounter:
    """Fast, cached token counter using `tiktoken` with deterministic offline fallback."""

    _ENCODERS: ClassVar[dict[str, Any]] = {}
    _FALLBACK_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        """Initialize the counter with the requested BPE encoding name."""
        self.encoding_name = encoding_name
        self._encoder = self._get_encoder(encoding_name)

    @classmethod
    def _get_encoder(cls, encoding_name: str) -> Any | None:
        if not HAS_TIKTOKEN or tiktoken is None:
            return None
        if encoding_name in cls._ENCODERS:
            return cls._ENCODERS[encoding_name]
        try:
            enc = tiktoken.get_encoding(encoding_name)
            cls._ENCODERS[encoding_name] = enc
            return enc
        except Exception:
            # Offline environment without cached tiktoken BPE ranks
            cls._ENCODERS[encoding_name] = None
            return None

    def count(self, text: str) -> int:
        """Return the token count of `text`."""
        if not text:
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text, disallowed_special=()))
            except Exception:
                pass
        # Deterministic byte-pair approximation when offline
        lexical_pieces = len(self._FALLBACK_TOKEN_RE.findall(text))
        byte_estimate = max(1, len(text.encode("utf-8")) // 4)
        return max(lexical_pieces, byte_estimate)


class MultiResolutionElider:
    """Generates the 4 discrete AST fidelity tiers and token counts for source files."""

    _BLANK_LINES_RE: ClassVar[re.Pattern[str]] = re.compile(r"\n{3,}")

    def __init__(self, token_counter: TokenCounter | None = None) -> None:
        """Initialize the elider with a `TokenCounter` instance."""
        self.token_counter = token_counter or TokenCounter()

    def process_files(self, files: list[FileAnalysis]) -> None:
        """Populate `raw_tokens`, `rendered_tiers`, and `tier_tokens` for all `files`."""
        for file_obj in files:
            self.populate_tiers(file_obj)

    def populate_tiers(self, file_obj: FileAnalysis) -> None:
        """Compute all 4 fidelity tiers and their token costs for a single `FileAnalysis`."""
        full_text = file_obj.sanitized_content.strip()
        if full_text:
            full_text += "\n"

        full_tokens = self.token_counter.count(full_text)
        file_obj.raw_tokens = full_tokens

        skeleton_text = self.render_skeleton_with_docstrings(file_obj, full_text)
        skeleton_tokens = self.token_counter.count(skeleton_text)

        # Ensure skeleton never exceeds full source cost
        if skeleton_tokens > full_tokens or not skeleton_text.strip():
            skeleton_text = full_text
            skeleton_tokens = full_tokens

        signatures_text = self.render_signatures_only(file_obj, skeleton_text)
        signatures_tokens = self.token_counter.count(signatures_text)

        # Enforce strict monotonic token cost: TREE_ONLY <= SIGNATURES <= SKELETON <= FULL
        if signatures_tokens > skeleton_tokens or not signatures_text.strip():
            signatures_text = skeleton_text
            signatures_tokens = skeleton_tokens

        file_obj.rendered_tiers = {
            FidelityLevel.TREE_ONLY: "",
            FidelityLevel.SIGNATURES_ONLY: signatures_text,
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: skeleton_text,
            FidelityLevel.FULL_SOURCE: full_text,
        }
        file_obj.tier_tokens = {
            FidelityLevel.TREE_ONLY: 0,
            FidelityLevel.SIGNATURES_ONLY: signatures_tokens,
            FidelityLevel.SKELETON_WITH_DOCSTRINGS: skeleton_tokens,
            FidelityLevel.FULL_SOURCE: full_tokens,
        }

    @classmethod
    def render_skeleton_with_docstrings(
        cls,
        file_obj: FileAnalysis,
        full_text: str,
    ) -> str:
        """Render `FidelityLevel.SKELETON_WITH_DOCSTRINGS` via reverse byte-range elision."""
        source = file_obj.sanitized_content
        if not source.strip():
            return ""

        elidable_ranges = cls._collect_non_overlapping_body_ranges(file_obj.symbols)
        if not elidable_ranges:
            return full_text

        raw_bytes = source.encode("utf-8")
        extractor = get_extractor(file_obj.language)
        buffer = bytearray(raw_bytes)

        # Replace implementation bodies in reverse byte order so earlier byte offsets never shift!
        for span in sorted(elidable_ranges, key=lambda r: r.start_byte, reverse=True):
            if (
                span.start_byte < 0
                or span.end_byte > len(buffer)
                or span.start_byte >= span.end_byte
            ):
                continue

            replacement_str = extractor.elision_marker(span)
            buffer[span.start_byte : span.end_byte] = replacement_str.encode("utf-8")

        elided_text = buffer.decode("utf-8", errors="replace").strip()
        if not extractor.PRESERVE_WHITESPACE:
            elided_text = cls._BLANK_LINES_RE.sub("\n\n", elided_text)
        return f"{elided_text}\n" if elided_text else full_text

    @classmethod
    def render_signatures_only(
        cls,
        file_obj: FileAnalysis,
        skeleton_fallback: str,
    ) -> str:
        """Render `FidelityLevel.SIGNATURES_ONLY` containing imports and public declarations."""
        extractor = get_extractor(file_obj.language)
        outline = extractor.render_signatures(file_obj.sanitized_content, file_obj.symbols)
        if outline is not None:
            return outline

        if not file_obj.symbols:
            return skeleton_fallback

        output_lines: list[str] = []

        # 1. Include up to 12 key import statements
        if file_obj.imports:
            for imp in file_obj.imports[:12]:
                clean_imp = " ".join(imp.split())
                output_lines.append(clean_imp)
            if len(file_obj.imports) > 12:
                output_lines.append(
                    f"# ... ({len(file_obj.imports) - 12} additional imports omitted)"
                )
            output_lines.append("")

        # 2. Emit symbol declarations (prioritizing exported symbols, or all if none exported)
        exported_symbols = [
            s
            for s in file_obj.symbols
            if s.is_exported or s.name in {"__init__", "__call__", "main"}
        ]
        target_symbols = exported_symbols if exported_symbols else file_obj.symbols

        for sym in target_symbols:
            indent = "    " if sym.parent_symbol else ""
            for dec in sym.decorators:
                output_lines.append(f"{indent}{dec}")

            output_lines.append(f"{indent}{extractor.render_signature(sym)}")

        rendered = "\n".join(output_lines).strip()
        return f"{rendered}\n" if rendered else skeleton_fallback

    @staticmethod
    def _collect_non_overlapping_body_ranges(symbols: list[SymbolNode]) -> list[ByteRange]:
        """Return outermost non-overlapping language-selected elision spans."""
        candidates = [
            sym.body_range
            for sym in symbols
            if sym.body_range is not None and sym.body_range.byte_length > 16
        ]
        if not candidates:
            return []

        # Sort by start_byte ascending, and by larger end_byte first on ties
        sorted_spans = sorted(candidates, key=lambda r: (r.start_byte, -r.end_byte))
        accepted: list[ByteRange] = []

        for span in sorted_spans:
            if not accepted:
                accepted.append(span)
                continue
            prev = accepted[-1]
            # Skip nested function bodies that are already inside an enclosing elided body
            if span.start_byte >= prev.start_byte and span.end_byte <= prev.end_byte:
                continue
            if span.start_byte >= prev.end_byte:
                accepted.append(span)

        return accepted
