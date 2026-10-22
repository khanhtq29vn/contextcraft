from __future__ import annotations

from pathlib import Path

from contextcraft import ContextCraft


def test_languages_compile_with_strict_budgets(
    tmp_path: Path, language_case: tuple[str, str, bytes, str, list[str]]
) -> None:
    language_id, path, source, _, _ = language_case
    (tmp_path / path).write_bytes(source)
    compiler = ContextCraft()
    for budget in (64, 256, 2048):
        result = compiler.compile(tmp_path, budget_tokens=budget)
        assert result.files[0].language == language_id
        assert result.stats.compressed_tokens <= budget
        assert result.files[0].parsed.source == source
