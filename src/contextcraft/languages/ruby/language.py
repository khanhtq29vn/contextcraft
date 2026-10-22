from __future__ import annotations

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.ruby.extraction import RubyExtractor
from contextcraft.languages.ruby.signatures import SignaturesBuilder
from contextcraft.languages.ruby.skeleton import SkeletonBuilder


class RubyLanguage(Language):
    spec = LanguageSpec(
        id="ruby",
        parser_id="ruby",
        extensions=frozenset({".rb", ".rake", ".gemspec"}),
        filenames=frozenset({"Gemfile", "Rakefile", "Guardfile"}),
        ignore_patterns=("vendor/", "Gemfile.lock"),
    )
    extractor = RubyExtractor
    skeleton_builder = SkeletonBuilder
    signatures_builder = SignaturesBuilder
