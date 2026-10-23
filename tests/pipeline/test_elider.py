from __future__ import annotations

from unittest.mock import patch

import pytest
import tiktoken

from contextcraft.ast import ParsedAst
from contextcraft.ast.parser import parse
from contextcraft.elider import (
    Elider,
    FidelityLevel,
    RenderedTier,
    TokenCounter,
)
from contextcraft.formatter import ArtifactFormatter
from contextcraft.languages.base import Language, LanguageSpec, SignaturesBuilder, SkeletonBuilder
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.models import CompilationConfig


class CharacterCounter:
    def count(self, text: str) -> int:
        return len(text)


def test_elider_supplies_a_default_token_counter(encoder: tiktoken.Encoding) -> None:
    with patch("contextcraft.elider.tiktoken.get_encoding", return_value=encoder):
        elider = Elider()
    source = b"function run(value) { return transform(value); }"
    parsed = parse(source, JavaScriptLanguage)

    tiers = elider.render(parsed, JavaScriptLanguage)

    assert isinstance(elider.token_counter, TokenCounter)
    assert tiers[FidelityLevel.FULL].tokens == len(source)
    for tier in tiers.values():
        assert tier.tokens == len(encoder.encode(tier.content, disallowed_special=()))


def test_elider_and_formatter_preserve_falsy_injected_counters() -> None:
    class Counter:
        def __bool__(self) -> bool:
            return False

        def count(self, text: str) -> int:
            return len(text)

    counter = Counter()
    with patch("contextcraft.elider.tiktoken.get_encoding") as get_encoding:
        elider = Elider(counter)
        formatter = ArtifactFormatter(CompilationConfig(), counter)

    assert elider.token_counter is formatter.token_counter is counter
    get_encoding.assert_not_called()


@pytest.mark.parametrize(
    "source,skeleton,signatures,expected_skeleton,expected_signatures",
    [
        ("full source", "skel", "sig", "skel", "sig"),
        ("full source", "larger than full source", "sig", "full source", "sig"),
        ("full source", "skel", "larger signatures", "skel", "skel"),
        ("full source", "", "sig", "full source", "sig"),
        ("full source", "skel", " \n ", "skel", "skel"),
        ("", "skel", "sig", "", ""),
    ],
)
def test_elider_enforces_monotonic_tiers(
    source: str,
    skeleton: str,
    signatures: str,
    expected_skeleton: str,
    expected_signatures: str,
) -> None:
    class TestSkeletonBuilder(SkeletonBuilder):
        def build(self, parsed: ParsedAst) -> str:
            return skeleton

    class TestSignaturesBuilder(SignaturesBuilder):
        def build(self, parsed: ParsedAst) -> str:
            return signatures

    class TestLanguage(Language):
        spec = LanguageSpec(id="test")
        skeleton_builder = TestSkeletonBuilder
        signatures_builder = TestSignaturesBuilder

    parsed = ParsedAst(source=source.encode())
    tiers = Elider(CharacterCounter()).render(parsed, TestLanguage)

    assert list(tiers) == list(FidelityLevel)
    assert tiers[FidelityLevel.TREE] == RenderedTier("", 0)
    assert tiers[FidelityLevel.FULL].content == source
    assert tiers[FidelityLevel.SKELETON].content == expected_skeleton
    assert tiers[FidelityLevel.SIGNATURES].content == expected_signatures
    costs = [tiers[level].tokens for level in FidelityLevel]
    assert costs == sorted(costs)
    for tier in tiers.values():
        assert tier.tokens == len(tier.content)
    assert parsed.source == source.encode()


def test_elider_uses_injected_token_costs_not_character_lengths() -> None:
    class TestSkeletonBuilder(SkeletonBuilder):
        def build(self, parsed: ParsedAst) -> str:
            return "long skeleton"

    class TestSignaturesBuilder(SignaturesBuilder):
        def build(self, parsed: ParsedAst) -> str:
            return "sig"

    class TestLanguage(Language):
        spec = LanguageSpec(id="test")
        skeleton_builder = TestSkeletonBuilder
        signatures_builder = TestSignaturesBuilder

    class Counter:
        def count(self, text: str) -> int:
            return {"full": 20, "long skeleton": 5, "sig": 9}[text]

    tiers = Elider(Counter()).render(ParsedAst(source=b"full"), TestLanguage)

    assert tiers[FidelityLevel.FULL] == RenderedTier("full", 20)
    assert tiers[FidelityLevel.SKELETON] == RenderedTier("long skeleton", 5)
    assert tiers[FidelityLevel.SIGNATURES] is tiers[FidelityLevel.SKELETON]


@pytest.mark.parametrize("source", [b"", b"const value = input;", b"function broken( {"])
def test_elider_preserves_source_without_safe_summaries(source: bytes) -> None:
    parsed = parse(source, JavaScriptLanguage)
    tiers = Elider(CharacterCounter()).render(parsed, JavaScriptLanguage)

    for level in (FidelityLevel.FULL, FidelityLevel.SKELETON, FidelityLevel.SIGNATURES):
        assert tiers[level].content == source.decode()
