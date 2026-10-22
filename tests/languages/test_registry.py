from __future__ import annotations

import importlib

import pytest

from contextcraft.languages.base import Language, LanguageSpec
from contextcraft.languages.builtin import CppLanguage, default_registry
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.languages.registry import LanguageRegistry


def test_registry_registers_and_gets_languages() -> None:
    registry = LanguageRegistry()
    registry.register(JavaScriptLanguage)

    assert registry.get("javascript") is JavaScriptLanguage
    assert registry.get("unknown") is None


@pytest.mark.parametrize("path", ["app.js", "src/app.mjs", "app.cjs", "app.jsx", "src/APP.JS"])
def test_registry_detects_javascript_extensions(path: str) -> None:
    registry = LanguageRegistry()
    registry.register(JavaScriptLanguage)

    assert registry.detect_candidates(path) == [JavaScriptLanguage]


def test_registry_rejects_duplicate_ids_without_changing_candidates() -> None:
    registry = LanguageRegistry()
    registry.register(JavaScriptLanguage)

    class DuplicateLanguage(Language):
        spec = LanguageSpec(id="javascript", extensions=frozenset({".other"}))

    with pytest.raises(ValueError, match="Duplicate language: javascript"):
        registry.register(DuplicateLanguage)

    assert registry.get("javascript") is JavaScriptLanguage
    assert registry.detect_candidates("app.js") == [JavaScriptLanguage]
    assert registry.detect_candidates("app.other") == []


def test_registry_prefers_filenames_and_preserves_candidate_order() -> None:
    class FirstLanguage(Language):
        spec = LanguageSpec(id="first", extensions=frozenset({".js"}))

    class SecondLanguage(Language):
        spec = LanguageSpec(
            id="second",
            extensions=frozenset({".js"}),
            filenames=frozenset({"special.js", "Buildfile"}),
        )

    registry = LanguageRegistry()
    registry.register(FirstLanguage)
    registry.register(SecondLanguage)

    assert registry.detect_candidates("src/app.js") == [FirstLanguage, SecondLanguage]
    assert registry.detect_candidates("src/special.js") == [SecondLanguage]
    assert registry.detect_candidates("src/Buildfile") == [SecondLanguage]
    assert registry.detect_candidates("src/buildfile") == []
    assert registry.detect_candidates("unknown.txt") == []


def test_registry_returns_independent_candidate_lists() -> None:
    class TestLanguage(Language):
        spec = LanguageSpec(
            id="test",
            extensions=frozenset({".test"}),
            filenames=frozenset({"Testfile"}),
        )

    registry = LanguageRegistry()
    registry.register(TestLanguage)

    for path in ("app.test", "Testfile"):
        candidates = registry.detect_candidates(path)
        candidates.clear()
        assert registry.detect_candidates(path) == [TestLanguage]

    assert LanguageRegistry().get("test") is None


def test_registry_aliases_and_ignore_aggregation_are_transactional() -> None:
    class FirstLanguage(Language):
        spec = LanguageSpec(
            id="first",
            aliases=("alias",),
            extensions=frozenset({".X", ".x"}),
            ignore_patterns=("generated/",),
        )

    class DuplicateLanguage(Language):
        spec = LanguageSpec(
            id="second",
            aliases=("alias",),
            extensions=frozenset({".second"}),
            ignore_patterns=("other/",),
        )

    registry = LanguageRegistry()
    registry.register(FirstLanguage)
    assert registry.get("alias") is FirstLanguage
    assert registry.languages == (FirstLanguage,)
    assert registry.ignore_patterns == ("generated/",)
    assert registry.detect_candidates("file.X") == [FirstLanguage]

    with pytest.raises(ValueError, match="Duplicate language"):
        registry.register(DuplicateLanguage)

    assert registry.get("second") is None
    assert registry.ignore_patterns == ("generated/",)
    assert registry.detect_candidates("file.second") == []


def test_cpp_headers_are_shared_candidates() -> None:
    candidates = default_registry().detect_candidates("service.h")

    assert len(candidates) == 2
    assert CppLanguage in candidates


@pytest.mark.parametrize("language", default_registry().languages, ids=lambda lang: lang.spec.id)
def test_languages_have_dedicated_components(language: type) -> None:
    package = f"contextcraft.languages.{language.spec.id}"
    assert language.__module__ == package + ".language"
    assert language.extractor.__module__ == package + ".extraction"
    assert language.skeleton_builder.__module__ == package + ".skeleton"
    assert language.signatures_builder.__module__ == package + ".signatures"
    for module in ("language", "extraction", "skeleton", "signatures"):
        importlib.import_module(f"{package}.{module}")


@pytest.mark.parametrize(
    "language_id,path",
    [
        ("ruby", "Gemfile"),
        ("ruby", "Rakefile"),
        ("ruby", "task.rake"),
        ("ruby", "project.gemspec"),
        ("php", "view.phtml"),
        ("hcl", "config.hcl"),
        ("hcl", "terraform.tfvars"),
        ("cmake", "modules/common.cmake"),
        ("graphql", "schema.gql"),
    ],
)
def test_language_filename_detection(language_id: str, path: str) -> None:
    registry = default_registry()
    assert registry.detect_candidates(path) == [registry.get(language_id)]


@pytest.mark.parametrize("alias,language_id", [("proto", "protobuf"), ("c_sharp", "csharp")])
def test_registry_accepts_parser_name_aliases(alias: str, language_id: str) -> None:
    registry = default_registry()
    assert registry.get(alias) is registry.get(language_id)
