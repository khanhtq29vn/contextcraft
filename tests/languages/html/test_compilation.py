from __future__ import annotations

from pathlib import Path

from contextcraft import ContextCraft
from contextcraft.elider import FidelityLevel, TokenCounter


def test_html_embedded_pipeline_preserves_full_source_and_token_budgets(tmp_path: Path) -> None:
    source = (
        b"<main><p>Introductory text</p><script>function run(value) {\n"
        + b"    service(value);\n" * 30
        + b"}</script><style>.card { color: red; margin: 10px; padding: 20px; }</style></main>"
    )
    (tmp_path / "index.html").write_bytes(source)
    compiler = ContextCraft()
    analyzed = compiler.analyze_repository(tmp_path)[0]
    assert analyzed.tiers[FidelityLevel.FULL].content == source.decode()
    assert "service(value)" not in analyzed.tiers[FidelityLevel.SKELETON].content
    assert "color: red" not in analyzed.tiers[FidelityLevel.SKELETON].content
    assert len(analyzed.parsed.embedded_regions) == 2
    for budget in (64, 256, 1024):
        result = compiler.compile(tmp_path, budget_tokens=budget)
        assert TokenCounter().count(result.content) <= budget
