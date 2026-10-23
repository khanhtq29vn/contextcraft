from __future__ import annotations

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import ElixirLanguage


def test_elixir_definitions_keep_guards_docs_and_native_syntax() -> None:
    source = (
        "defmodule Client do\r\n use App.Base\r\n alias App.{Service, Other}\r\n"
        ' @doc "Run café documentation."\r\n'
        " def run(value \\\\ 1) when is_integer(value) do\r\n service(value)\r\n end\r\n"
        " def ready, do: done()\r\n defp secret, do: :hidden\r\n"
        " defmacro build(value), do: quote(do: unquote(value))\r\nend\r\n"
    ).encode()
    parsed = parse(source, ElixirLanguage)
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}
    skeleton = ElixirLanguage.skeleton_builder(ElixirLanguage.spec).build(parsed)
    signatures = ElixirLanguage.signatures_builder(ElixirLanguage.spec).build(parsed)

    assert not parsed.has_errors
    assert set(symbols) == {"Client", "Client.run", "Client.ready", "Client.secret", "Client.build"}
    docstring = symbols["Client.run"].docstring_range
    assert docstring is not None
    assert "Run café documentation." in parsed.text(docstring)
    assert "Run café documentation." in skeleton
    assert "when is_integer(value)" in skeleton
    assert "service(value)" not in skeleton
    assert "done()" not in skeleton
    assert "secret" not in signatures
    assert "defmacro build(value)" in signatures
    assert signatures.startswith(
        "defmodule Client do\n    use App.Base\n    alias App.{Service, Other}\n"
    )
    assert signatures.count("alias App.{Service, Other}") == 1
    assert not parse(skeleton.encode(), ElixirLanguage).has_errors
    assert not parse(signatures.encode(), ElixirLanguage).has_errors
    for reference in parsed.scope_graph.references:
        if reference.name == "value":
            assert reference.scope.resolve("value") is not None
    assert parsed.source == source


def test_elixir_inline_modules_and_destructured_parameters() -> None:
    source = b"defmodule Client, do: (def run([head | tail], %{value: value}), do: {head, tail, value})\n"
    parsed = parse(source, ElixirLanguage)
    signatures = ElixirLanguage.signatures_builder(ElixirLanguage.spec).build(parsed)

    assert not parsed.has_errors
    assert signatures.startswith("defmodule Client do\n")
    assert not parse(signatures.encode(), ElixirLanguage).has_errors
    references = [
        ref for ref in parsed.scope_graph.references if ref.name in {"head", "tail", "value"}
    ]
    assert references
    assert all(ref.scope.resolve(ref.name) is not None for ref in references)


def test_elixir_imports_ignore_dynamic_arguments_and_expand_grouped_aliases() -> None:
    source = b'alias App.{Service, Other}\nrequire Logger\nuse App.Base\nimport module_name\nservice("not_a_module")\n'
    parsed = parse(source, ElixirLanguage)

    assert not parsed.has_errors
    assert [item.module for item in parsed.imports] == [
        "App.Service",
        "App.Other",
        "Logger",
        "App.Base",
    ]
