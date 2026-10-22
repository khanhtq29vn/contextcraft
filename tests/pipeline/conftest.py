from __future__ import annotations

import pytest
import tiktoken


@pytest.fixture
def encoder() -> tiktoken.Encoding:
    return tiktoken.Encoding(
        name="test_bytes",
        pat_str=r"[\s\S]",
        mergeable_ranks={bytes([value]): value for value in range(256)},
        special_tokens={"<|endoftext|>": 256},
    )
