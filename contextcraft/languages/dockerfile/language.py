from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.dockerfile.extraction import DockerfileExtractor
from contextcraft.languages.dockerfile.signatures import SignaturesBuilder
from contextcraft.languages.dockerfile.skeleton import SkeletonBuilder


class DockerfileLanguage(Language):
    spec = LanguageSpec(
        id="dockerfile",
        parser_id="dockerfile",
        filenames=frozenset({"Dockerfile", "dockerfile"}),
    )
    extractor = DockerfileExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
