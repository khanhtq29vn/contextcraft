from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import tiktoken

from contextcraft.elider import TokenCounter


@pytest.mark.parametrize("text", ["", "hello, world!", "你好 café", "<|endoftext|>"])
def test_token_counter_uses_tiktoken(encoder: tiktoken.Encoding, text: str) -> None:
    with patch("contextcraft.elider.tiktoken.get_encoding", return_value=encoder) as get_encoding:
        counter = TokenCounter()

    assert counter.encoding_name == "cl100k_base"
    get_encoding.assert_called_once_with("cl100k_base")
    assert counter.count(text) == len(encoder.encode(text, disallowed_special=()))


def test_token_counter_accepts_custom_encoding(encoder: tiktoken.Encoding) -> None:
    with patch("contextcraft.elider.tiktoken.get_encoding", return_value=encoder) as get_encoding:
        counter = TokenCounter("o200k_base")

    get_encoding.assert_called_once_with("o200k_base")
    assert counter.encoding_name == "o200k_base"
    assert counter.count("example") == 7


def test_token_counter_rejects_invalid_encoding() -> None:
    with (
        patch(
            "contextcraft.elider.tiktoken.get_encoding", side_effect=ValueError("Unknown encoding")
        ),
        pytest.raises(ValueError, match="Unknown encoding"),
    ):
        TokenCounter("invalid")


@pytest.mark.parametrize("text", ["", "hello, world!", "你好 café", " " * 40, "\ud800"])
def test_token_counter_has_deterministic_offline_fallback(text: str) -> None:
    with patch("contextcraft.elider.tiktoken.get_encoding", side_effect=OSError("offline")):
        first = TokenCounter()
        second = TokenCounter()

    assert first.count(text) == first.count(text) == second.count(text)
    assert first.count("") == 0
    if text:
        assert first.count(text) > 0
        assert first.count(text) >= len(text.encode("utf-8", errors="replace")) // 4


def test_token_counter_falls_back_when_encoding_fails() -> None:
    encoder = Mock(spec=tiktoken.Encoding)
    encoder.encode.side_effect = RuntimeError("encoding failed")
    with patch("contextcraft.elider.tiktoken.get_encoding", return_value=encoder):
        counter = TokenCounter()

    assert counter.count("") == 0
    encoder.encode.assert_not_called()
    assert counter.count("hello, world!") == 4
    encoder.encode.assert_called_once_with("hello, world!", disallowed_special=())
