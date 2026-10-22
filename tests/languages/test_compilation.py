from __future__ import annotations

from pathlib import Path

import pytest

from contextcraft import ContextCraft


@pytest.mark.parametrize("budget", [64, 256, 2048])
def test_languages_compile_with_strict_budgets(
    tmp_path: Path, language_files: dict[str, tuple[str, bytes]], budget: int
) -> None:
    for path, (_, source) in language_files.items():
        (tmp_path / path).write_bytes(source)

    result = ContextCraft(budget_tokens=budget).compile(tmp_path)

    assert result.stats.compressed_tokens <= budget
    assert {file.rel_path for file in result.files} == set(language_files)
    for file in result.files:
        language_id, source = language_files[file.rel_path]
        assert file.language == language_id
        assert file.parsed.source == source
