from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.graphql.extraction import GraphQLExtractor
from contextcraft.languages.graphql.signatures import SignaturesBuilder
from contextcraft.languages.graphql.skeleton import SkeletonBuilder


class GraphQLLanguage(Language):
    spec = LanguageSpec(
        id="graphql",
        parser_id="graphql",
        extensions=frozenset({".graphql", ".gql"}),
    )
    extractor = GraphQLExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
