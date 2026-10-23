from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.bash.extraction import BashExtractor
from contextcraft.languages.bash.signatures import SignaturesBuilder
from contextcraft.languages.bash.skeleton import SkeletonBuilder


class BashLanguage(Language):
    spec = LanguageSpec(
        id="bash",
        parser_id="bash",
        extensions=frozenset({".sh", ".bash", ".zsh"}),
    )
    extractor = BashExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
