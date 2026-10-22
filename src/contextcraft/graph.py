"""Dependency graph construction and Personalized PageRank centrality scoring.

Inspired by `Aider-AI/aider`'s `repomap.py`, this module constructs a weighted
directed multigraph $G = (V, E)$ where vertices represent repository files and
directed edges $(u \\to v)$ capture cross-file module imports and symbol references.

Centrality is computed via a pure-Python Personalized PageRank power-iteration
solver (zero SciPy dependency) biased toward:
1. User-specified `focus_files` and `focus_query` keywords (BM25 lexical scoring)
2. 1-hop graph neighbors of focus-matched files
3. Architectural entrypoints (`core.py`, `main.py`, `pyproject.toml`, `README.md`, etc.)
"""

from __future__ import annotations

import fnmatch
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import ClassVar

import networkx as nx

from contextcraft.models import CompilationConfig, FileAnalysis


class DependencyGraphScorer:
    """Builds a cross-file reference graph and computes Personalized PageRank scores."""

    _QUERY_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_]{2,}")

    # Baseline structural priors for high-signal architectural entrypoints
    _ARCHITECTURAL_FILENAME_PRIORS: ClassVar[dict[str, float]] = {
        "readme.md": 1.8,
        "pyproject.toml": 1.6,
        "package.json": 1.6,
        "cargo.toml": 1.6,
        "go.mod": 1.5,
        "core.py": 1.9,
        "main.py": 1.8,
        "app.py": 1.7,
        "cli.py": 1.6,
        "models.py": 1.8,
        "schema.py": 1.7,
        "schemas.py": 1.7,
        "optimizer.py": 1.7,
        "elider.py": 1.7,
        "graph.py": 1.7,
        "index.ts": 1.7,
        "index.tsx": 1.7,
        "main.rs": 1.8,
        "lib.rs": 1.8,
        "main.go": 1.8,
    }

    def __init__(self, config: CompilationConfig | None = None) -> None:
        """Initialize the scorer with compilation configuration."""
        self.config = config or CompilationConfig()

    def score_files(self, files: list[FileAnalysis]) -> nx.MultiDiGraph[str]:
        """Build the dependency graph and populate `pagerank_score` on each `FileAnalysis`.

        Returns the constructed `nx.MultiDiGraph` for inspection or testing.
        """
        if not files:
            return nx.MultiDiGraph()

        if len(files) == 1:
            files[0].relevance_boost = 1.0
            files[0].pagerank_score = 1.0
            single_graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
            single_graph.add_node(files[0].rel_path)
            return single_graph

        graph = self.build_dependency_graph(files)
        query_terms = self._tokenize_query(self.config.focus_query)
        personalization = self._compute_personalization_vector(files, graph, query_terms)

        for file_obj in files:
            file_obj.relevance_boost = personalization.get(file_obj.rel_path, 1.0)

        raw_ranks = self._run_pagerank(graph, personalization)

        total_rank = sum(raw_ranks.values())
        if total_rank <= 0.0:
            uniform = 1.0 / len(files)
            for file_obj in files:
                file_obj.pagerank_score = uniform
        else:
            for file_obj in files:
                file_obj.pagerank_score = raw_ranks.get(file_obj.rel_path, 0.0) / total_rank

        return graph

    def build_dependency_graph(self, files: list[FileAnalysis]) -> nx.MultiDiGraph[str]:
        """Construct a directed multigraph where edges $(u \\to v)$ mean $u$ depends on $v$."""
        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()

        # Index 1: symbol identifier -> set of defining file rel_paths
        symbol_definers: dict[str, set[str]] = defaultdict(set)
        # Index 2: module alias / stem -> set of file rel_paths
        module_index: dict[str, set[str]] = defaultdict(set)

        for file_obj in files:
            rel_path = file_obj.rel_path
            graph.add_node(rel_path)

            for ident in file_obj.defined_identifiers:
                symbol_definers[ident].add(rel_path)
            for sym in file_obj.symbols:
                symbol_definers[sym.name].add(rel_path)
                if sym.qualified_name:
                    symbol_definers[sym.qualified_name].add(rel_path)

            for mod_key in self._module_keys_for_path(rel_path):
                module_index[mod_key].add(rel_path)

        query_terms = set(self._tokenize_query(self.config.focus_query))
        num_files = len(files)

        for src_file in files:
            src_path = src_file.rel_path

            # 1. Explicit module import edges (high confidence)
            imported_targets = self._resolve_imported_files(src_file, module_index)
            for dst_path in imported_targets:
                if dst_path != src_path:
                    graph.add_edge(
                        src_path,
                        dst_path,
                        weight=6.0,
                        ident="__import__",
                    )
                    # Reverse coupling edge so callers of core modules also gain structural signal
                    graph.add_edge(
                        dst_path,
                        src_path,
                        weight=0.9,
                        ident="__imported_by__",
                    )

            # 2. Cross-file symbol reference edges (weighted by specificity & IDF)
            ref_counts = Counter(src_file.referenced_identifiers)
            for ident, freq in ref_counts.items():
                definers = symbol_definers.get(ident)
                if not definers:
                    continue

                ident_weight = self._compute_identifier_weight(
                    ident=ident,
                    definer_count=len(definers),
                    total_files=num_files,
                    query_terms=query_terms,
                )
                edge_weight = ident_weight * math.sqrt(freq)

                for dst_path in definers:
                    if dst_path == src_path:
                        continue
                    graph.add_edge(
                        src_path,
                        dst_path,
                        weight=edge_weight,
                        ident=ident,
                    )
                    graph.add_edge(
                        dst_path,
                        src_path,
                        weight=edge_weight * 0.15,
                        ident=f"caller:{ident}",
                    )

        return graph

    @classmethod
    def _compute_identifier_weight(
        cls,
        *,
        ident: str,
        definer_count: int,
        total_files: int,
        query_terms: set[str],
    ) -> float:
        """Score an identifier reference using Aider-style specificity heuristics and IDF."""
        weight = 1.0

        is_snake = "_" in ident and any(ch.isalpha() for ch in ident)
        is_camel = any(ch.isupper() for ch in ident) and any(ch.islower() for ch in ident)

        if (is_snake or is_camel) and len(ident) >= 8:
            weight *= 4.0
        elif len(ident) >= 6:
            weight *= 2.0

        if ident.startswith("_"):
            weight *= 0.2

        if definer_count > 5:
            weight *= 0.15
        elif definer_count > 1:
            weight *= 1.0 / math.sqrt(definer_count)
        elif total_files > 3:
            weight *= 1.5

        ident_lower = ident.lower()
        if query_terms and any(
            term == ident_lower or term in ident_lower for term in query_terms
        ):
            weight *= 6.0

        return weight

    def _compute_personalization_vector(
        self,
        files: list[FileAnalysis],
        graph: nx.MultiDiGraph[str],
        query_terms: list[str],
    ) -> dict[str, float]:
        """Compute Personalized PageRank teleportation probabilities across all files."""
        base_scores: dict[str, float] = {}

        doc_freq: Counter[str] = Counter()
        file_term_bags: dict[str, tuple[set[str], set[str], set[str], set[str]]] = {}

        for file_obj in files:
            path_tokens = set(self._tokenize_query(file_obj.rel_path))
            sym_tokens: set[str] = set()
            doc_tokens: set[str] = set()
            for sym in file_obj.symbols:
                sym_tokens.update(self._tokenize_query(sym.name))
                sym_tokens.update(self._tokenize_query(sym.signature))
                if sym.docstring:
                    doc_tokens.update(self._tokenize_query(sym.docstring))
            body_tokens = {ident.lower() for ident in file_obj.referenced_identifiers}

            file_term_bags[file_obj.rel_path] = (
                path_tokens,
                sym_tokens,
                doc_tokens,
                body_tokens,
            )

            all_file_terms = path_tokens | sym_tokens | doc_tokens | body_tokens
            for q_term in query_terms:
                if any(q_term == t or q_term in t for t in all_file_terms):
                    doc_freq[q_term] += 1

        num_files = len(files)

        for file_obj in files:
            rel_path = file_obj.rel_path
            filename_lower = PurePosixPath(rel_path).name.lower()

            # 1. Architectural entrypoint prior
            score = self._ARCHITECTURAL_FILENAME_PRIORS.get(filename_lower, 1.0)

            # Deprioritize test/benchmark files slightly unless explicitly focused
            if rel_path.startswith(("tests/", "test_", "benchmarks/")) or "/test_" in rel_path:
                score *= 0.65

            # 2. Explicit focus_files glob/path match
            if self._matches_focus_files(rel_path, self.config.focus_files):
                score += 20.0

            # 3. Lexical BM25-inspired query match
            if query_terms:
                path_toks, sym_toks, doc_toks, body_toks = file_term_bags[rel_path]
                query_match_score = 0.0
                for q_term in query_terms:
                    df = doc_freq.get(q_term, 0)
                    idf = math.log(1.0 + (num_files - df + 0.5) / (df + 0.5))

                    term_weight = 0.0
                    if any(q_term == t or q_term in t for t in path_toks):
                        term_weight += 5.0
                    if any(q_term == t or q_term in t for t in sym_toks):
                        term_weight += 4.0
                    if any(q_term == t or q_term in t for t in doc_toks):
                        term_weight += 2.5
                    if any(q_term == t or q_term in t for t in body_toks):
                        term_weight += 1.0

                    query_match_score += term_weight * max(idf, 0.25)

                if query_match_score > 0.0:
                    score += query_match_score * 3.5

            base_scores[rel_path] = max(score, 0.05)

        # 4. 1-Hop Neighbor Diffusion: boost direct dependencies of high-relevance files
        diffused_scores = dict(base_scores)
        if query_terms or self.config.focus_files:
            median_score = sorted(base_scores.values())[len(base_scores) // 2]
            for node, node_score in base_scores.items():
                if node_score > median_score * 1.5:
                    excess = node_score - median_score
                    for _, neighbor, edge_data in graph.out_edges(node, data=True):
                        if neighbor != node:
                            edge_w = min(float(edge_data.get("weight", 1.0)), 10.0)
                            diffused_scores[neighbor] = (
                                diffused_scores.get(neighbor, 1.0)
                                + 0.30 * excess * (edge_w / 10.0)
                            )

        return diffused_scores

    @staticmethod
    def _run_pagerank(
        graph: nx.MultiDiGraph[str],
        personalization: dict[str, float],
        alpha: float = 0.85,
        max_iter: int = 200,
        tol: float = 1.0e-6,
    ) -> dict[str, float]:
        """Execute weighted Personalized PageRank via pure-Python power iteration.

        Avoids NetworkX's `scipy` binary dependency while faithfully implementing
        dangling-node mass redistribution and personalized teleportation:
        $$x^{(t)}(v) = \\left[(1 - \\alpha) + \\alpha S_{\\text{dangling}}\\right] p(v)
        + \\alpha \\sum_{u \\to v} x^{(t-1)}(u) \\frac{w(u, v)}{W_{\\text{out}}(u)}$$
        """
        nodes = list(graph.nodes())
        num_nodes = len(nodes)
        if num_nodes == 0:
            return {}

        # Normalize personalization vector p
        total_pers = sum(max(personalization.get(n, 0.0), 0.0) for n in nodes)
        if total_pers <= 0.0:
            p = dict.fromkeys(nodes, 1.0 / num_nodes)
        else:
            p = {n: max(personalization.get(n, 0.0), 0.0) / total_pers for n in nodes}

        # Collapse multigraph edges into normalized outgoing transition probabilities
        out_transitions: dict[str, list[tuple[str, float]]] = {}
        dangling_nodes: list[str] = []

        for u in nodes:
            agg_weights: dict[str, float] = defaultdict(float)
            for _, v, data in graph.out_edges(u, data=True):
                w = float(data.get("weight", 1.0))
                if w > 0.0:
                    agg_weights[str(v)] += w

            total_out = sum(agg_weights.values())
            if total_out <= 0.0:
                dangling_nodes.append(u)
                out_transitions[u] = []
            else:
                out_transitions[u] = [
                    (v, w / total_out) for v, w in agg_weights.items()
                ]

        ranks = dict(p)

        for _ in range(max_iter):
            prev_ranks = ranks
            dangling_mass = sum(prev_ranks[u] for u in dangling_nodes)
            base_factor = (1.0 - alpha) + (alpha * dangling_mass)

            next_ranks: dict[str, float] = {n: base_factor * p[n] for n in nodes}

            for u, transitions in out_transitions.items():
                if not transitions:
                    continue
                u_share = alpha * prev_ranks[u]
                for v, prob in transitions:
                    next_ranks[v] += u_share * prob

            ranks = next_ranks
            err = sum(abs(ranks[n] - prev_ranks[n]) for n in nodes)
            if err < num_nodes * tol:
                break

        return ranks

    @classmethod
    def _tokenize_query(cls, query: str | None) -> list[str]:
        """Split a natural-language query or identifier into normalized tokens."""
        if not query or not query.strip():
            return []

        raw_tokens = cls._QUERY_TOKEN_RE.findall(query)
        expanded: list[str] = []
        seen: set[str] = set()

        for tok in raw_tokens:
            sub_parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", tok).lower().split("_")
            for candidate in [tok.lower(), *sub_parts]:
                if len(candidate) >= 2 and candidate not in seen:
                    seen.add(candidate)
                    expanded.append(candidate)

        return expanded

    @staticmethod
    def _matches_focus_files(rel_path: str, focus_patterns: list[str]) -> bool:
        if not focus_patterns:
            return False
        filename = PurePosixPath(rel_path).name
        for pattern in focus_patterns:
            clean_pat = pattern.strip().lstrip("./")
            if not clean_pat:
                continue
            if (
                rel_path == clean_pat
                or filename == clean_pat
                or fnmatch.fnmatch(rel_path, clean_pat)
                or fnmatch.fnmatch(filename, clean_pat)
                or clean_pat in rel_path
            ):
                return True
        return False

    @staticmethod
    def _module_keys_for_path(rel_path: str) -> set[str]:
        """Generate candidate module import strings that resolve to `rel_path`."""
        posix = PurePosixPath(rel_path)
        without_ext = posix.with_suffix("").as_posix()
        keys: set[str] = {
            rel_path,
            without_ext,
            without_ext.replace("/", "."),
            posix.stem,
        }

        for prefix in ("src/", "lib/", "app/", "packages/"):
            if without_ext.startswith(prefix):
                trimmed = without_ext[len(prefix) :]
                keys.add(trimmed)
                keys.add(trimmed.replace("/", "."))

        if posix.stem == "__init__" and posix.parent.as_posix() != ".":
            pkg_path = posix.parent.as_posix()
            keys.add(pkg_path)
            keys.add(pkg_path.replace("/", "."))
            for prefix in ("src/", "lib/"):
                if pkg_path.startswith(prefix):
                    pkg_trimmed = pkg_path[len(prefix) :]
                    keys.add(pkg_trimmed)
                    keys.add(pkg_trimmed.replace("/", "."))

        return {k for k in keys if k and k != "."}

    @staticmethod
    def _resolve_imported_files(
        src_file: FileAnalysis,
        module_index: dict[str, set[str]],
    ) -> set[str]:
        """Match import lines in `src_file` to target `rel_path`s in the repository."""
        resolved: set[str] = set()
        src_dir = PurePosixPath(src_file.rel_path).parent.as_posix()

        py_from_re = re.compile(r"^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+(.+)$")
        py_import_re = re.compile(r"^\s*import\s+([A-Za-z0-9_.,\s]+)$")
        js_import_re = re.compile(r"""(?:from|import)\s+["']([^"']+)["']""")

        for imp_line in src_file.imports:
            candidates: list[str] = []

            m_from = py_from_re.match(imp_line)
            if m_from:
                mod_name = m_from.group(1).lstrip(".")
                imported_names = [
                    part.strip().split(" as ")[0].strip()
                    for part in m_from.group(2).strip("() ").split(",")
                ]
                if mod_name:
                    candidates.append(mod_name)
                    for name in imported_names:
                        if name:
                            candidates.append(f"{mod_name}.{name}")

            m_imp = py_import_re.match(imp_line)
            if m_imp:
                for part in m_imp.group(1).split(","):
                    mod_name = part.strip().split(" as ")[0].strip()
                    if mod_name:
                        candidates.append(mod_name)

            for m_js in js_import_re.finditer(imp_line):
                raw_spec = m_js.group(1)
                if raw_spec.startswith("."):
                    joined = os.path.normpath(os.path.join(src_dir, raw_spec)).replace("\\", "/")
                    candidates.append(joined.lstrip("./"))
                else:
                    candidates.append(raw_spec)

            for cand in candidates:
                if cand in module_index:
                    resolved.update(module_index[cand])

        return resolved
