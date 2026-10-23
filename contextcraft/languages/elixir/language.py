from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.elixir.extraction import ElixirExtractor
from contextcraft.languages.elixir.signatures import SignaturesBuilder
from contextcraft.languages.elixir.skeleton import SkeletonBuilder


class ElixirLanguage(Language):
    spec = LanguageSpec(
        id="elixir",
        parser_id="elixir",
        extensions=frozenset({".ex", ".exs"}),
        ignore_patterns=("_build/", "deps/", ".elixir_ls/", "mix.lock"),
    )
    extractor = ElixirExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
