from __future__ import annotations

from pathlib import Path

from contextcraft import ContextCraft
from contextcraft.graph import DependencyGraphScorer


def test_graph_resolves_python_relative_and_javascript_index_imports(tmp_path: Path) -> None:
    paths = {
        "src/auth/service.py": "from .models import User\n",
        "src/auth/models.py": "class User:\n    pass\n",
        "src/client.js": 'import {helper} from "./helpers"; helper();',
        "src/helpers/index.js": "export function helper() { return 1; }",
    }
    for name, text in paths.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    files = ContextCraft().analyze_repository(tmp_path)
    graph = DependencyGraphScorer().build_dependency_graph(files)

    for source, target in (
        ("src/auth/service.py", "src/auth/models.py"),
        ("src/client.js", "src/helpers/index.js"),
    ):
        assert any(data["ident"] == "__import__" for data in graph[source][target].values())


def test_pagerank_ranks_core_dependencies_above_leaf_utilities(sample_repo: Path) -> None:
    """Verify `src/auth/models.py` and `src/auth/jwt_service.py` outrank `src/utils/helpers.py`."""
    cc = ContextCraft()
    analyses = cc.analyze_repository(sample_repo)

    pr_by_path = {f.rel_path: f.pagerank_score for f in analyses}
    total_pr = sum(pr_by_path.values())

    assert abs(total_pr - 1.0) < 1e-5
    assert pr_by_path["src/auth/models.py"] > pr_by_path["src/utils/helpers.py"]
    assert pr_by_path["src/auth/jwt_service.py"] > pr_by_path["src/utils/helpers.py"]


def test_personalized_pagerank_focus_query_and_focus_files(sample_repo: Path) -> None:
    """Verify `focus_query` and `focus_files` shift PageRank centrality toward target modules."""
    cc = ContextCraft()

    baseline = {f.rel_path: f.pagerank_score for f in cc.analyze_repository(sample_repo)}
    focused_jwt = {
        f.rel_path: f.pagerank_score
        for f in cc.analyze_repository(
            sample_repo,
            focus_query="JWT verify_token revocation hmac",
        )
    }
    assert focused_jwt["src/auth/jwt_service.py"] > baseline["src/auth/jwt_service.py"]

    focused_leaf = {
        f.rel_path: f.pagerank_score
        for f in cc.analyze_repository(
            sample_repo,
            focus_files=["src/utils/helpers.py"],
        )
    }
    assert focused_leaf["src/utils/helpers.py"] > baseline["src/utils/helpers.py"] * 2.0
