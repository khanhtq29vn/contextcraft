from __future__ import annotations

import fnmatch
import math
import posixpath
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import ClassVar

import networkx as nx

from contextcraft.models import CompilationConfig, FileAnalysis
from contextcraft.retention import code_symbols


class DependencyGraphScorer:
    _QUERY_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"\w{2,}")
    _BM25_K1 = 1.2
    _BM25_B = 0.75
    _FIELD_WEIGHTS = (5.0, 4.0, 2.5, 1.0)
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
        self.config = config or CompilationConfig()

    def score_files(self, files: list[FileAnalysis]) -> nx.MultiDiGraph[str]:
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
        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        symbol_definers: dict[str, set[str]] = defaultdict(set)
        module_index: dict[str, set[str]] = defaultdict(set)
        for file_obj in files:
            rel_path = file_obj.rel_path
            graph.add_node(rel_path)
            for binding in file_obj.parsed.scope_graph.bindings:
                if binding.scope.kind == "module":
                    symbol_definers[binding.name].add(rel_path)
            for sym in code_symbols(file_obj.parsed, public_only=False):
                if sym.name is not None:
                    symbol_definers[sym.name].add(rel_path)
                if sym.qualified_name:
                    symbol_definers[sym.qualified_name].add(rel_path)
            for mod_key in self._module_keys_for_path(rel_path):
                module_index[mod_key].add(rel_path)
        query_terms = set(self._tokenize_query(self.config.focus_query))
        num_files = len(files)
        for src_file in files:
            src_path = src_file.rel_path
            imported_targets = self._resolve_imported_files(src_file, module_index)
            # Unfocused tests must not gain centrality just by importing production code.
            include_reverse_edges = self._test_penalty(src_path) == 1.0
            for dst_path in imported_targets:
                if dst_path != src_path:
                    graph.add_edge(src_path, dst_path, weight=6.0, ident="__import__")
                    if include_reverse_edges:
                        graph.add_edge(dst_path, src_path, weight=0.9, ident="__imported_by__")
            ref_counts = Counter(
                reference.name
                for reference in src_file.parsed.scope_graph.references
                if reference.scope.resolve(reference.name) is None
            )
            for ident, freq in ref_counts.items():
                definers = symbol_definers.get(ident)
                if not definers:
                    continue
                definers = definers & imported_targets or definers
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
                    graph.add_edge(src_path, dst_path, weight=edge_weight, ident=ident)
                    if include_reverse_edges:
                        graph.add_edge(
                            dst_path, src_path, weight=edge_weight * 0.15, ident=f"caller:{ident}"
                        )
        return graph

    @classmethod
    def _compute_identifier_weight(
        cls, *, ident: str, definer_count: int, total_files: int, query_terms: set[str]
    ) -> float:
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
        if query_terms and any(term == ident_lower or term in ident_lower for term in query_terms):
            weight *= 6.0
        return weight

    def _bm25_scores(self, files: list[FileAnalysis], query_terms: list[str]) -> dict[str, float]:
        """BM25F normalizes fields before saturating their combined term frequency."""
        scores = dict.fromkeys((file.rel_path for file in files), 0.0)
        if not files or not query_terms:
            return scores

        documents: list[list[Counter[str]]] = []
        doc_freq: Counter[str] = Counter()
        for file in files:
            symbols = code_symbols(file.parsed, public_only=False)
            fields = (
                file.rel_path,
                "\n".join(file.parsed.text(symbol.signature_range) for symbol in symbols),
                "\n".join(
                    file.parsed.text(symbol.docstring_range)
                    for symbol in symbols
                    if symbol.docstring_range is not None
                ),
                file.parsed.source.decode("utf-8"),
            )
            tokens = [Counter(self._tokenize(field)) for field in fields]
            documents.append(tokens)
            doc_freq.update(set().union(*tokens))

        lengths = [[sum(field.values()) for field in document] for document in documents]
        averages = [sum(column) / len(files) for column in zip(*lengths, strict=True)]
        for file, document, field_lengths in zip(files, documents, lengths, strict=True):
            for term in dict.fromkeys(query_terms):
                frequency = doc_freq[term]
                if not frequency:
                    continue
                idf = math.log1p((len(files) - frequency + 0.5) / (frequency + 0.5))
                normalized_tf = 0.0
                for field, length, average, weight in zip(
                    document, field_lengths, averages, self._FIELD_WEIGHTS, strict=True
                ):
                    if field[term]:
                        normalization = 1 - self._BM25_B + self._BM25_B * length / average
                        normalized_tf += weight * field[term] / normalization
                scores[file.rel_path] += (
                    idf * normalized_tf * (self._BM25_K1 + 1) / (normalized_tf + self._BM25_K1)
                )
        return scores

    def _compute_personalization_vector(
        self, files: list[FileAnalysis], graph: nx.MultiDiGraph[str], query_terms: list[str]
    ) -> dict[str, float]:
        base_scores: dict[str, float] = {}
        lexical_scores = self._bm25_scores(files, query_terms)
        for file_obj in files:
            rel_path = file_obj.rel_path
            filename = PurePosixPath(rel_path).name
            score = self._ARCHITECTURAL_FILENAME_PRIORS.get(filename.lower(), 1.0)
            score += 3.5 * lexical_scores[rel_path]
            explicitly_focused = self._matches_focus_files(rel_path, self.config.focus_files)
            score *= self._test_penalty(rel_path)
            if explicitly_focused:
                score += 20.0
            base_scores[rel_path] = max(score, 0.05)
        diffused_scores = dict(base_scores)
        if query_terms or self.config.focus_files:
            median_score = sorted(base_scores.values())[len(base_scores) // 2]
            for node, node_score in base_scores.items():
                if node_score > median_score * 1.5:
                    excess = node_score - median_score
                    neighbors: dict[str, float] = defaultdict(float)
                    for _, neighbor, edge_data in graph.out_edges(node, data=True):
                        if neighbor != node:
                            neighbors[neighbor] += max(float(edge_data.get("weight", 1.0)), 0.0)
                    total_weight = sum(neighbors.values())
                    if total_weight:
                        for neighbor, weight in neighbors.items():
                            diffused_scores[neighbor] += 0.3 * excess * weight / total_weight
        return diffused_scores

    def _test_penalty(self, rel_path: str) -> float:
        if self._matches_focus_files(rel_path, self.config.focus_files) or (
            set(self._tokenize_query(self.config.focus_query))
            & {
                "test",
                "tests",
                "testing",
                "spec",
                "specs",
                "benchmark",
                "benchmarks",
                "benchmarking",
            }
        ):
            return 1.0
        path = PurePosixPath(rel_path)
        if {part.lower() for part in path.parts[:-1]} & {
            "test",
            "tests",
            "__tests__",
            "spec",
            "specs",
            "__specs__",
            "benchmarks",
            "benches",
        } or re.search(r"(^(?:test|spec)[_.]|[._](?:test|spec)\.|Tests?\.)", path.name):
            return 0.02
        return 1.0

    @staticmethod
    def _run_pagerank(
        graph: nx.MultiDiGraph[str],
        personalization: dict[str, float],
        alpha: float = 0.85,
        max_iter: int = 200,
        tol: float = 1e-06,
    ) -> dict[str, float]:
        nodes = list(graph.nodes())
        num_nodes = len(nodes)
        if num_nodes == 0:
            return {}
        total_pers = sum(max(personalization.get(n, 0.0), 0.0) for n in nodes)
        if total_pers <= 0.0:
            p = dict.fromkeys(nodes, 1.0 / num_nodes)
        else:
            p = {n: max(personalization.get(n, 0.0), 0.0) / total_pers for n in nodes}
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
                out_transitions[u] = [(v, w / total_out) for v, w in agg_weights.items()]
        ranks = dict(p)
        for _ in range(max_iter):
            prev_ranks = ranks
            dangling_mass = sum(prev_ranks[u] for u in dangling_nodes)
            base_factor = 1.0 - alpha + alpha * dangling_mass
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
    def _tokenize(cls, text: str) -> list[str]:
        tokens: list[str] = []
        for word in cls._QUERY_TOKEN_RE.findall(text):
            split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", word)
            split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", split)
            tokens.extend(
                token
                for token in dict.fromkeys([word.lower(), *split.lower().split("_")])
                if len(token) >= 2
            )
        return tokens

    @classmethod
    def _tokenize_query(cls, query: str | None) -> list[str]:
        return list(dict.fromkeys(cls._tokenize(query or "")))

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
                or (clean_pat in rel_path)
            ):
                return True
        return False

    @staticmethod
    def _module_keys_for_path(rel_path: str) -> set[str]:
        posix = PurePosixPath(rel_path)
        without_ext = posix.with_suffix("").as_posix()
        keys: set[str] = {rel_path, without_ext, without_ext.replace("/", "."), posix.stem}
        for prefix in ("src/", "lib/", "app/", "packages/"):
            if without_ext.startswith(prefix):
                trimmed = without_ext[len(prefix) :]
                keys.add(trimmed)
                keys.add(trimmed.replace("/", "."))
        if (
            posix.stem in {"__init__", "index", "mod"} or posix.suffix == ".go"
        ) and posix.parent.as_posix() != ".":
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
        src_file: FileAnalysis, module_index: dict[str, set[str]]
    ) -> set[str]:
        resolved: set[str] = set()
        directory = PurePosixPath(src_file.rel_path).parent
        for item in src_file.parsed.imports:
            module = item.module
            statement = src_file.parsed.text(item.declaration_range)
            candidates: list[str] = []
            py_from = re.match(r"from\s+([.\w]+)\s+import\s+(.+)", statement, re.DOTALL)
            if py_from:
                module = py_from.group(1)
                if module.startswith("."):
                    levels = len(module) - len(module.lstrip("."))
                    base = directory
                    for _ in range(levels - 1):
                        base = base.parent
                    module = posixpath.normpath(
                        posixpath.join(base.as_posix(), module.lstrip(".").replace(".", "/"))
                    )
                    separator = "/"
                else:
                    separator = "."
                candidates.append(module)
                for part in py_from.group(2).strip("() \n").split(","):
                    imported = part.strip().split(" as ")[0]
                    if imported and imported != "*":
                        candidates.append(module + separator + imported)
            elif module.startswith("."):
                candidates.append(posixpath.normpath(posixpath.join(directory.as_posix(), module)))
            else:
                candidates.extend(
                    [module, posixpath.normpath(posixpath.join(directory.as_posix(), module))]
                )
                rust = re.match(r"(?:pub\s+)?use\s+([^;{]+)", statement)
                if rust:
                    parts = (
                        rust.group(1)
                        .strip()
                        .removeprefix("crate::")
                        .replace("::", ".")
                        .rstrip(".")
                        .split(".")
                    )
                    candidates.extend(".".join(parts[:end]) for end in range(1, len(parts) + 1))
                declaration = re.match(r"(?:import|using)\s+(?:static\s+)?([\w.]+)", statement)
                if declaration:
                    candidates.append(declaration.group(1))
            for candidate in candidates:
                resolved.update(module_index.get(candidate, ()))
        return resolved
