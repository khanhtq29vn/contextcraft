"""Build file dependency graphs and rank files for a focus query."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import rustworkx as rx

from contextcraft.config import Config
from contextcraft.models import ImportResolution, Index, Source

_TOKEN_RE = re.compile(r"\w{2,}")
_FIELD_WEIGHTS = (5.0, 4.0, 2.5, 1.0)
_BM25_K1 = 1.2
_BM25_B = 0.75


class GraphBuilder:
    """Build a directed file graph from resolved imports."""

    def build(
        self, index: Index, source: Source, resolutions: list[ImportResolution]
    ) -> rx.PyDiGraph:
        """Connect each indexed file to the files it imports.

        Args:
            index: Files to include, even when their source was not loaded.
            source: Imports referenced by the resolution records.
            resolutions: Resolved imports with target file IDs from index.

        Returns:
            A directed graph with file IDs as node payloads. Each edge points
            from an importing file to a dependency and has weight 1.0. Duplicate
            edges, self-imports, and ambiguous targets are omitted.
        """
        graph = rx.PyDiGraph(multigraph=False)
        nodes = {file_id: graph.add_node(file_id) for file_id in sorted(index.files)}
        edges = set()

        for resolution in resolutions:
            source_file_id = source.imports[resolution.import_id].source_file_id

            for target in resolution.target_file_ids:
                if source_file_id != target:
                    edges.add((nodes[source_file_id], nodes[target]))

        graph.add_edges_from((source, target, 1.0) for source, target in sorted(edges))

        return graph


class GraphScorer:
    """Rank files by dependency importance and relevance to the focus query."""

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = []

        for word in _TOKEN_RE.findall(text):
            split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", word)
            split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", split)
            tokens.extend(
                token
                for token in dict.fromkeys([word.lower(), *split.lower().split("_")])
                if len(token) >= 2
            )

        return tokens

    def _bm25_scores(
        self, index: Index, source: Source, query_terms: list[str]
    ) -> dict[int, float]:
        scores = dict.fromkeys(index.files, 0.0)

        if not index.files or not query_terms:
            return scores

        documents = {}
        doc_freq: Counter[str] = Counter()

        for file_id, file in index.files.items():
            content = source.content.get(file_id)
            language = (
                index.languages[file.language_id]
                if file.language_id is not None
                else None
            )

            signatures = ""

            if language is not None and content is not None:
                signatures = language.render_sigs(content, source.analyses[file_id])

            fields = (
                file.path.relative_to(index.path).as_posix(),
                signatures,
                "\n".join(source.docstrings.get(file_id, ())),
                content.decode("utf-8") if content is not None else "",
            )

            tokens = [Counter(self._tokenize(field)) for field in fields]
            documents[file_id] = tokens
            doc_freq.update(set().union(*tokens))

        lengths = {
            file_id: [sum(field.values()) for field in fields]
            for file_id, fields in documents.items()
        }

        count = len(documents)
        averages = [
            sum(values[index] for values in lengths.values()) / count
            for index in range(len(_FIELD_WEIGHTS))
        ]

        for file_id, fields in documents.items():
            for term in dict.fromkeys(query_terms):
                frequency = doc_freq[term]

                if not frequency:
                    continue

                idf = math.log1p((count - frequency + 0.5) / (frequency + 0.5))
                normalized_tf = 0.0

                for field, length, average, weight in zip(
                    fields, lengths[file_id], averages, _FIELD_WEIGHTS
                ):
                    if field[term]:
                        normalization = 1 - _BM25_B + _BM25_B * length / average
                        normalized_tf += weight * field[term] / normalization

                scores[file_id] += (
                    idf * normalized_tf * (_BM25_K1 + 1) / (normalized_tf + _BM25_K1)
                )

        return scores

    @staticmethod
    def _diffuse_preferences(
        graph: rx.PyDiGraph, preferences: dict[int, float]
    ) -> dict[int, float]:
        diffused = dict(preferences)

        if not preferences:
            return diffused

        median = sorted(preferences.values())[len(preferences) // 2]

        for node, preference in preferences.items():
            if preference <= 1.5 * median:
                continue

            neighbors: dict[int, float] = defaultdict(float)

            for _, target, payload in graph.out_edges(node):
                weight = float(payload)

                if target != node and weight > 0:
                    neighbors[target] += weight

            total_weight = sum(neighbors.values())

            if total_weight:
                excess = preference - median

                for target, weight in neighbors.items():
                    diffused[target] += 0.3 * excess * weight / total_weight

        return diffused

    def score(
        self, index: Index, source: Source, graph: rx.PyDiGraph, config: Config
    ) -> dict[int, float]:
        """Return personalized PageRank scores keyed by file ID.

        Args:
            index: Files and focus-file matches for this analysis.
            source: Loaded content and docstrings used for query matching.
            graph: Dependency graph with index file IDs as node payloads.
            config: Focus query used to favor matches in paths, signatures,
                docstrings, and source.

        Returns:
            A score for each file in the graph, or an empty mapping if the graph
            is empty. Higher scores give files more weight during allocation.

        Raises:
            KeyError: If query matching encounters a missing language or analysis.
        """
        if graph.num_nodes() == 0:
            return {}

        query_terms = list(dict.fromkeys(self._tokenize(config.focus_query or "")))
        lexical_scores = self._bm25_scores(index, source, query_terms)
        preferences = {
            node: 1.0
            + (graph[node] in index.focus_file_ids)
            + 3.5 * lexical_scores[graph[node]]
            for node in graph.node_indices()
        }

        if query_terms or index.focus_file_ids:
            preferences = self._diffuse_preferences(graph, preferences)

        total = sum(preferences.values())
        preferences = {node: weight / total for node, weight in preferences.items()}
        ranks = rx.pagerank(
            graph,
            alpha=0.85,
            personalization=preferences,
            dangling=preferences,
            weight_fn=float,
        )

        return {graph[node]: score for node, score in ranks.items()}
