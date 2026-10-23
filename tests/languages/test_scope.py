from __future__ import annotations

import pytest

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


@pytest.mark.parametrize(
    "language_id", ["ruby", "php", "swift", "kotlin", "scala", "lua", "r", "elixir", "zig"]
)
def test_native_function_parameters_resolve_in_function_scopes(
    language_id: str, language_sources: dict[str, bytes]
) -> None:
    language = default_registry().get(language_id)
    assert language is not None
    source = language_sources[language_id]
    parsed = parse(source, language)
    name = "$value" if language_id == "php" else "value"
    references = [
        reference for reference in parsed.scope_graph.references if reference.name == name
    ]
    assert references
    for reference in references:
        binding = reference.scope.resolve(name)
        assert binding is not None
        assert binding.scope.kind in {"function", "method"}
