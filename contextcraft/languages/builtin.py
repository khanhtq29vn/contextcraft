from __future__ import annotations

from contextcraft.languages.bash.language import BashLanguage as BashLanguage
from contextcraft.languages.c.language import CLanguage as CLanguage
from contextcraft.languages.cmake.language import CMakeLanguage as CMakeLanguage
from contextcraft.languages.cpp.language import CppLanguage as CppLanguage
from contextcraft.languages.csharp.language import CSharpLanguage as CSharpLanguage
from contextcraft.languages.css.language import CSSLanguage as CSSLanguage
from contextcraft.languages.dockerfile.language import DockerfileLanguage as DockerfileLanguage
from contextcraft.languages.elixir.language import ElixirLanguage as ElixirLanguage
from contextcraft.languages.go.language import GoLanguage as GoLanguage
from contextcraft.languages.graphql.language import GraphQLLanguage as GraphQLLanguage
from contextcraft.languages.hcl.language import HCLLanguage as HCLLanguage
from contextcraft.languages.html.language import HTMLLanguage as HTMLLanguage
from contextcraft.languages.java.language import JavaLanguage as JavaLanguage
from contextcraft.languages.javascript.language import JavaScriptLanguage as JavaScriptLanguage
from contextcraft.languages.json.language import JSONLanguage as JSONLanguage
from contextcraft.languages.kotlin.language import KotlinLanguage as KotlinLanguage
from contextcraft.languages.lua.language import LuaLanguage as LuaLanguage
from contextcraft.languages.make.language import MakefileLanguage as MakefileLanguage
from contextcraft.languages.markdown.language import MarkdownLanguage as MarkdownLanguage
from contextcraft.languages.php.language import PHPLanguage as PHPLanguage
from contextcraft.languages.protobuf.language import ProtobufLanguage as ProtobufLanguage
from contextcraft.languages.python.language import PythonLanguage as PythonLanguage
from contextcraft.languages.r.language import RLanguage as RLanguage
from contextcraft.languages.registry import LanguageRegistry
from contextcraft.languages.rst.language import RSTLanguage as RSTLanguage
from contextcraft.languages.ruby.language import RubyLanguage as RubyLanguage
from contextcraft.languages.rust.language import RustLanguage as RustLanguage
from contextcraft.languages.scala.language import ScalaLanguage as ScalaLanguage
from contextcraft.languages.scss.language import SCSSLanguage as SCSSLanguage
from contextcraft.languages.sql.language import SQLLanguage as SQLLanguage
from contextcraft.languages.swift.language import SwiftLanguage as SwiftLanguage
from contextcraft.languages.text.language import TextLanguage as TextLanguage
from contextcraft.languages.toml.language import TOMLLanguage as TOMLLanguage
from contextcraft.languages.tsx.language import TSXLanguage as TSXLanguage
from contextcraft.languages.typescript.language import TypeScriptLanguage as TypeScriptLanguage
from contextcraft.languages.yaml.language import YAMLLanguage as YAMLLanguage
from contextcraft.languages.zig.language import ZigLanguage as ZigLanguage


def default_registry() -> LanguageRegistry:
    registry = LanguageRegistry()
    for language in (
        JavaScriptLanguage,
        PythonLanguage,
        TypeScriptLanguage,
        TSXLanguage,
        RustLanguage,
        GoLanguage,
        JavaLanguage,
        CLanguage,
        CppLanguage,
        CSharpLanguage,
        JSONLanguage,
        YAMLLanguage,
        TOMLLanguage,
        HTMLLanguage,
        CSSLanguage,
        SCSSLanguage,
        RubyLanguage,
        PHPLanguage,
        SwiftLanguage,
        KotlinLanguage,
        ScalaLanguage,
        LuaLanguage,
        RLanguage,
        SQLLanguage,
        BashLanguage,
        MarkdownLanguage,
        RSTLanguage,
        ProtobufLanguage,
        GraphQLLanguage,
        HCLLanguage,
        DockerfileLanguage,
        MakefileLanguage,
        CMakeLanguage,
        ElixirLanguage,
        ZigLanguage,
    ):
        registry.register(language)
    return registry
