from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.php.extraction import PHPExtractor
from contextcraft.languages.php.signatures import SignaturesBuilder
from contextcraft.languages.php.skeleton import SkeletonBuilder


class PHPLanguage(Language):
    spec = LanguageSpec(
        id="php",
        parser_id="php",
        extensions=frozenset({".php", ".phtml"}),
        ignore_patterns=("vendor/", "composer.lock"),
    )
    extractor = PHPExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
