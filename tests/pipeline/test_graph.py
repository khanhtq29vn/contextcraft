from __future__ import annotations

import math
from pathlib import Path

import networkx as nx
import pytest

from contextcraft import ContextCraft
from contextcraft.ast import ParsedAst
from contextcraft.graph import DependencyGraphScorer
from contextcraft.models import CompilationConfig, FileAnalysis


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


def test_bm25_matches_formula_and_saturates_term_frequency() -> None:
    files = [
        FileAnalysis(name, name, "text", len(text), ParsedAst(text.encode()))
        for name, text in (
            ("a.txt", "needle needle filler"),
            ("b.txt", "needle filler filler"),
            ("c.txt", "other other other"),
        )
    ]
    scorer = DependencyGraphScorer()
    scores = scorer._bm25_scores(files, ["needle"])
    idf = math.log1p((3 - 2 + 0.5) / (2 + 0.5))

    assert scores["a.txt"] == pytest.approx(idf * 2 * 2.2 / (2 + 1.2))
    assert scores["b.txt"] == pytest.approx(idf)
    assert scores["b.txt"] < scores["a.txt"] < 2 * scores["b.txt"]
    assert scores["c.txt"] == 0
    assert scorer._bm25_scores(files, ["needle", "needle"]) == scores
    assert scorer._bm25_scores(files, []) == dict.fromkeys(scores, 0)
    assert scorer._bm25_scores([], ["needle"]) == {}


def test_bm25_normalizes_length_and_weights_rare_terms() -> None:
    files = [
        FileAnalysis(name, name, "text", len(text), ParsedAst(text.encode()))
        for name, text in (
            ("a.txt", "needle rare"),
            ("b.txt", "needle " + "filler " * 100),
            ("c.txt", "needle filler"),
        )
    ]
    scorer = DependencyGraphScorer()
    common = scorer._bm25_scores(files, ["needle"])
    rare = scorer._bm25_scores(files, ["rare"])

    assert common["a.txt"] > common["b.txt"]
    assert rare["a.txt"] > common["a.txt"]
    assert scorer._bm25_scores(files, ["need"]) == dict.fromkeys(common, 0)


def test_tokenization_preserves_frequency_and_splits_code_identifiers() -> None:
    scorer = DependencyGraphScorer()
    tokens = scorer._tokenize("HTTPServer auth_token auth_token café")

    assert {"httpserver", "http", "server", "auth_token", "auth", "token", "café"} <= set(tokens)
    assert tokens.count("auth") == 2
    assert scorer._tokenize_query("auth_token auth_token").count("auth") == 1


def test_neighbor_diffusion_is_bounded_and_only_one_hop() -> None:
    files = [
        FileAnalysis(name, name, "text", len(text), ParsedAst(text.encode()))
        for name, text in (("a.txt", "needle"), ("b.txt", "other"), ("c.txt", "other"))
    ]
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    graph.add_nodes_from(file.rel_path for file in files)
    scorer = DependencyGraphScorer(CompilationConfig(focus_query="needle"))
    base = scorer._compute_personalization_vector(files, graph, ["needle"])
    for _ in range(100):
        graph.add_edge("a.txt", "b.txt", weight=6.0)
    graph.add_edge("b.txt", "c.txt", weight=6.0)
    diffused = scorer._compute_personalization_vector(files, graph, ["needle"])

    assert diffused["b.txt"] - base["b.txt"] == pytest.approx(0.3 * (base["a.txt"] - 1))
    assert diffused["a.txt"] == base["a.txt"]
    assert diffused["c.txt"] == base["c.txt"]


def test_tests_are_deprioritized_unless_explicitly_focused() -> None:
    for path in (
        "tests/auth.py",
        "pkg/test_auth.py",
        "auth.test.ts",
        "auth.spec.js",
        "AuthTest.java",
        "auth_test.go",
    ):
        assert DependencyGraphScorer()._test_penalty(path) < 1
        assert (
            DependencyGraphScorer(CompilationConfig(focus_query="auth tests"))._test_penalty(path)
            == 1
        )
        assert DependencyGraphScorer(CompilationConfig(focus_files=[path]))._test_penalty(path) == 1
    assert DependencyGraphScorer()._test_penalty("src/auth.py") == 1


def test_graph_does_not_link_local_bindings_or_document_headings(tmp_path: Path) -> None:
    (tmp_path / "local.py").write_text("def run(value):\n    return value\n")
    (tmp_path / "other.py").write_text("value = 42\n")
    (tmp_path / "README.md").write_text("# value\n")
    files = ContextCraft().analyze_repository(tmp_path)
    graph = DependencyGraphScorer().build_dependency_graph(files)

    assert not graph.has_edge("local.py", "other.py")
    assert not graph.has_edge("local.py", "README.md")


def test_graph_prefers_imported_definitions_over_unrelated_same_named_symbols(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("class Service: pass\n")
    (tmp_path / "b.py").write_text("class Service: pass\n")
    (tmp_path / "client.py").write_text("from a import Service\ndef run(): return Service()\n")
    files = ContextCraft().analyze_repository(tmp_path)
    graph = DependencyGraphScorer().build_dependency_graph(files)

    assert graph.has_edge("client.py", "a.py")
    assert not graph.has_edge("client.py", "b.py")


def test_unfocused_tests_do_not_gain_pagerank_through_reverse_dependencies(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "optimizer.py").write_text("def optimize(value): return value\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_optimizer.py").write_text(
        "from src.optimizer import optimize\ndef test_optimize(): assert optimize(1) == 1\n"
    )
    files = ContextCraft().analyze_repository(tmp_path)
    by_path = {file.rel_path: file for file in files}
    source, test = "src/optimizer.py", "tests/test_optimizer.py"
    scorer = DependencyGraphScorer(CompilationConfig(focus_query="optimizer"))
    graph = scorer.score_files(files)
    unfocused_rank = by_path[test].pagerank_score

    assert graph.has_edge(test, source)
    assert not graph.has_edge(source, test)
    assert by_path[source].pagerank_score > 20 * unfocused_rank
    for config in (
        CompilationConfig(focus_query="optimizer testing"),
        CompilationConfig(focus_query="optimizer", focus_files=[test]),
    ):
        graph = DependencyGraphScorer(config).score_files(files)
        assert graph.has_edge(source, test)
        assert by_path[test].pagerank_score > unfocused_rank
