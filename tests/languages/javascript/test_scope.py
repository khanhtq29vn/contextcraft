from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.javascript.language import JavaScriptLanguage


def test_javascript_scopes_distinguish_var_and_block_bindings() -> None:
    parsed = parse(
        b"""
const outer = 1;
function run(arg) {
    if (arg) { var shared = outer; let local = arg; }
    return shared;
}
""",
        JavaScriptLanguage,
    )
    graph = parsed.scope_graph
    module, function, block = graph.scopes

    assert module.kind == "module"
    assert function.kind == "function"
    assert function.parent is module
    assert block.parent is function
    assert set(module.bindings) == {"outer", "run"}
    assert set(function.bindings) == {"arg", "shared"}
    assert set(block.bindings) == {"local"}
    assert [(ref.name, ref.scope.kind) for ref in graph.references] == [
        ("arg", "function"),
        ("outer", "block"),
        ("arg", "block"),
        ("shared", "function"),
    ]
    for binding in graph.bindings:
        assert binding.scope.bindings[binding.name] is binding
    for reference in graph.references:
        assert any(item is reference for item in reference.scope.references)


def test_javascript_destructuring_and_defaults() -> None:
    parsed = parse(
        b"""
const {a, key: alias, b = init, [key()]: value, ...rest} = data;
let [x, y = fallback(), ...tail] = values;
const run = ({option = defaultOption}, [arg], other = source) => use(option, arg, other);
""",
        JavaScriptLanguage,
    )

    assert set(parsed.defined_identifiers) == {
        "a",
        "alias",
        "b",
        "value",
        "rest",
        "x",
        "y",
        "tail",
        "run",
        "option",
        "arg",
        "other",
    }
    assert set(parsed.referenced_identifiers) == {
        "init",
        "key",
        "data",
        "fallback",
        "values",
        "defaultOption",
        "source",
        "use",
        "option",
        "arg",
        "other",
    }


def test_javascript_imports_exports_and_property_references() -> None:
    parsed = parse(
        b"""
import main, {remote as local, direct} from "pkg";
import * as ns from "mod";
export {local as renamed};
export {external as exported} from "other";
const object = {local, key: direct, [computed]: ns.member};
object[key] = main;
""",
        JavaScriptLanguage,
    )

    assert set(parsed.defined_identifiers) == {"main", "local", "direct", "ns", "object"}
    assert set(parsed.referenced_identifiers) == {
        "local",
        "direct",
        "computed",
        "ns",
        "object",
        "key",
        "main",
    }
    assert len(parsed.imports) == 3


def test_javascript_named_expressions_and_single_arrow_parameter() -> None:
    parsed = parse(
        b"""
const fn = function named(param) { return named(param); };
const double = value => value * factor;
const Type = class Inner { method(arg) { return new Inner(arg); } };
""",
        JavaScriptLanguage,
    )
    module = parsed.scope_graph.scopes[0]

    assert set(module.bindings) == {"fn", "double", "Type"}
    named = next(binding for binding in parsed.scope_graph.bindings if binding.name == "named")
    assert named.scope.kind == "function"
    assert set(named.scope.bindings) == {"named", "param"}
    inner = next(binding for binding in parsed.scope_graph.bindings if binding.name == "Inner")
    assert inner.scope.kind == "class"
    assert "value" in parsed.defined_identifiers
    assert "value" in parsed.referenced_identifiers
    assert "method" not in inner.scope.bindings


def test_javascript_loop_catch_switch_and_static_block_scopes() -> None:
    parsed = parse(
        b"""
for (let item of items) { use(item); }
for (var key in object) use(key);
try { work(); } catch ({message}) { log(message); }
switch (choice) { case selected: let local = choice; }
class Example { static { var hidden = init; } }
""",
        JavaScriptLanguage,
    )
    graph = parsed.scope_graph
    bindings = {binding.name: binding for binding in graph.bindings}

    assert bindings["item"].scope.kind == "loop"
    assert bindings["key"].scope.kind == "module"
    assert bindings["message"].scope.kind == "catch"
    assert bindings["local"].scope.kind == "block"
    assert bindings["hidden"].scope.kind == "static_block"
    assert "hidden" not in graph.scopes[0].bindings
    assert {"items", "object", "work", "log", "choice", "selected", "init"} <= set(
        parsed.referenced_identifiers
    )


def test_javascript_jsx_references() -> None:
    parsed = parse(
        b"const el = <div><Widget name={value}><ns.Part /></Widget></div>;", JavaScriptLanguage
    )

    assert [ref.name for ref in parsed.scope_graph.references] == ["Widget", "value", "ns"]


def test_javascript_computed_method_names_use_enclosing_scope() -> None:
    parsed = parse(
        b"class Example { [key](arg) { return arg; } [(() => nested)()]() {} } "
        b"const object = { [method]() {} };",
        JavaScriptLanguage,
    )
    graph = parsed.scope_graph
    module = graph.scopes[0]
    classes = [scope for scope in graph.scopes if scope.kind == "class"]
    assert len(classes) == 1
    class_scope = classes[0]
    assert class_scope.parent is module

    references = {ref.name: ref for ref in graph.references}
    assert references["key"].scope is class_scope
    assert references["method"].scope is module
    assert references["arg"].scope.kind == "function"
    assert references["nested"].scope.parent is class_scope


def test_language_exposes_scope_building() -> None:
    source = b"const value = input;"
    root = get_parser("javascript").parse(source).root_node
    graph = JavaScriptLanguage.build_scopes(root, source)

    assert [binding.name for binding in graph.bindings] == ["value"]
    assert [ref.name for ref in graph.references] == ["input"]
