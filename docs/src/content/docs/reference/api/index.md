---
title: "API reference"
description: "The API reference, written by plissken from the source."
editUrl: false
sidebar:
  order: 0
  hidden: true
---

## Python

- [`contextcraft`](contextcraft/): AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.
- [`contextcraft.__main__`](contextcraft/__main__/): Run the ContextCraft CLI with ``python -m contextcraft``.
- [`contextcraft._cli`](contextcraft/_cli/): Cyclopts commands and Rich output for the optional CLI extra.
- [`contextcraft.cli`](contextcraft/cli/): Load the optional Cyclopts and Rich command-line interface.

## Rust

- [`contextcraft-ai`](rust/contextcraft-ai/): Python bindings for AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.
- [`contextcraft-ai-core`](rust/contextcraft-ai-core/): AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.
- [`contextcraft-ai-core::error`](rust/contextcraft-ai-core/error/): Errors reported by repository analysis and artifact generation.
- [`contextcraft-ai-core::formatter`](rust/contextcraft-ai-core/formatter/): Render escaped Markdown, XML, or JSON and enforce the final token budget.
- [`contextcraft-ai-core::graph`](rust/contextcraft-ai-core/graph/): Directed local file dependencies and relevance scoring.
- [`contextcraft-ai-core::graph::scorer`](rust/contextcraft-ai-core/graph/scorer/)
- [`contextcraft-ai-core::index`](rust/contextcraft-ai-core/): Discover files, package ownership, and local workspace relationships.
- [`contextcraft-ai-core::languages`](rust/contextcraft-ai-core/languages/): Language grammars, outline capture queries, and local dependency resolution.
- [`contextcraft-ai-core::languages::bash`](rust/contextcraft-ai-core/languages/bash/): Bash `.sh` outlines and literal `source`/`.` dependencies.
- [`contextcraft-ai-core::languages::c`](rust/contextcraft-ai-core/languages/c/): C parsing and local include resolution with static compilation-database paths.
- [`contextcraft-ai-core::languages::c::dependencies`](rust/contextcraft-ai-core/languages/c/dependencies/): Extract dependency references from captured syntax nodes.
- [`contextcraft-ai-core::languages::c::resolve`](rust/contextcraft-ai-core/languages/c/resolve/): Resolve captured references to indexed local files.
- [`contextcraft-ai-core::languages::cmake`](rust/contextcraft-ai-core/languages/cmake/): CMake command/function/target outlines and static local file dependencies.
- [`contextcraft-ai-core::languages::component`](rust/contextcraft-ai-core/languages/component/): Shared embedded-language outlines and file dependencies for Vue and Svelte.
- [`contextcraft-ai-core::languages::cpp`](rust/contextcraft-ai-core/languages/cpp/): C++ parsing with shared C include resolution.
- [`contextcraft-ai-core::languages::csharp`](rust/contextcraft-ai-core/languages/csharp/): C# outlines, .NET project references, and solution membership.
- [`contextcraft-ai-core::languages::csharp::manifest`](rust/contextcraft-ai-core/languages/csharp/manifest/): .NET project references and solution membership, without evaluating MSBuild.
- [`contextcraft-ai-core::languages::css`](rust/contextcraft-ai-core/languages/css/): CSS selector/declaration outlines and literal local stylesheet imports.
- [`contextcraft-ai-core::languages::dockerfile`](rust/contextcraft-ai-core/languages/dockerfile/): Containerfile/Dockerfile outlines using `tree-sitter-containerfile`.
- [`contextcraft-ai-core::languages::elixir`](rust/contextcraft-ai-core/languages/elixir/): Elixir outlines, literal Mix dependencies, and local module references.
- [`contextcraft-ai-core::languages::elixir::dependencies`](rust/contextcraft-ai-core/languages/elixir/dependencies/): Literal Elixir module declarations, lexical aliases, and remote module references.
- [`contextcraft-ai-core::languages::elixir::manifest`](rust/contextcraft-ai-core/languages/elixir/manifest/): Literal Mix application names, path dependencies, and umbrella membership.
- [`contextcraft-ai-core::languages::go`](rust/contextcraft-ai-core/languages/go/): Go parsing, module discovery, and local import resolution.
- [`contextcraft-ai-core::languages::go::dependencies`](rust/contextcraft-ai-core/languages/go/dependencies/): Extract dependency references from captured syntax nodes.
- [`contextcraft-ai-core::languages::go::manifest`](rust/contextcraft-ai-core/languages/go/manifest/): Discover local package metadata and workspace relationships.
- [`contextcraft-ai-core::languages::go::resolve`](rust/contextcraft-ai-core/languages/go/resolve/): Resolve captured references to indexed local files.
- [`contextcraft-ai-core::languages::graphql`](rust/contextcraft-ai-core/languages/graphql/): GraphQL schema/operation outlines and explicitly imported local fragments.
- [`contextcraft-ai-core::languages::hcl`](rust/contextcraft-ai-core/languages/hcl/): HCL outlines and Terraform directory-module dependencies.
- [`contextcraft-ai-core::languages::html`](rust/contextcraft-ai-core/languages/html/): HTML structure, embedded JavaScript/CSS outlines, and literal local asset dependencies.
- [`contextcraft-ai-core::languages::javascript`](rust/contextcraft-ai-core/languages/javascript/): JavaScript outlines, local workspace packages, and static module resolution.
- [`contextcraft-ai-core::languages::javascript::dependencies`](rust/contextcraft-ai-core/languages/javascript/dependencies/): Extract dependency references from captured syntax nodes.
- [`contextcraft-ai-core::languages::javascript::manifest`](rust/contextcraft-ai-core/languages/javascript/manifest/): Discover local npm and pnpm package/workspace relationships.
- [`contextcraft-ai-core::languages::javascript::resolve`](rust/contextcraft-ai-core/languages/javascript/resolve/): Resolve captured references to indexed local files.
- [`contextcraft-ai-core::languages::json`](rust/contextcraft-ai-core/languages/json/): JSON key and scalar-value outlines.
- [`contextcraft-ai-core::languages::just`](rust/contextcraft-ai-core/languages/just/): Just outlines, explicit imports/modules, and named recipe dependencies.
- [`contextcraft-ai-core::languages::kotlin`](rust/contextcraft-ai-core/languages/kotlin/): Kotlin outlines, literal Gradle projects, and local package-qualified imports.
- [`contextcraft-ai-core::languages::kotlin::dependencies`](rust/contextcraft-ai-core/languages/kotlin/dependencies/): Kotlin package-qualified declarations and explicit imports.
- [`contextcraft-ai-core::languages::kotlin::manifest`](rust/contextcraft-ai-core/languages/kotlin/manifest/): Literal Gradle project includes, directory mappings, and project dependencies.
- [`contextcraft-ai-core::languages::local`](rust/contextcraft-ai-core/languages/local/): Shared mechanics for static, repository-local language resolution.
- [`contextcraft-ai-core::languages::lua`](rust/contextcraft-ai-core/languages/lua/): Lua outlines, LuaRocks metadata, and static local module dependencies.
- [`contextcraft-ai-core::languages::lua::manifest`](rust/contextcraft-ai-core/languages/lua/manifest/): Static LuaRocks package names and declared local rock dependencies.
- [`contextcraft-ai-core::languages::make`](rust/contextcraft-ai-core/languages/make/): Make outlines, literal includes, and source/target prerequisites.
- [`contextcraft-ai-core::languages::markdown`](rust/contextcraft-ai-core/languages/markdown/): Markdown document outlines and literal local links/assets.
- [`contextcraft-ai-core::languages::protobuf`](rust/contextcraft-ai-core/languages/protobuf/): Protocol Buffers schema outlines and repository-root-relative imports.
- [`contextcraft-ai-core::languages::python`](rust/contextcraft-ai-core/languages/python/): Python parsing, package discovery, and local import resolution.
- [`contextcraft-ai-core::languages::python::dependencies`](rust/contextcraft-ai-core/languages/python/dependencies/): Extract dependency references from captured syntax nodes.
- [`contextcraft-ai-core::languages::python::manifest`](rust/contextcraft-ai-core/languages/python/manifest/): Discover local package metadata and workspace relationships.
- [`contextcraft-ai-core::languages::python::resolve`](rust/contextcraft-ai-core/languages/python/resolve/): Resolve captured references to indexed local files.
- [`contextcraft-ai-core::languages::rst`](rust/contextcraft-ai-core/languages/rst/): reStructuredText outlines and literal local include dependencies.
- [`contextcraft-ai-core::languages::ruby`](rust/contextcraft-ai-core/languages/ruby/): Ruby `.rb` outlines, local Bundler gems, and literal load dependencies.
- [`contextcraft-ai-core::languages::ruby::manifest`](rust/contextcraft-ai-core/languages/ruby/manifest/): Literal gemspec names and Bundler local path dependencies, without evaluating Ruby.
- [`contextcraft-ai-core::languages::rust`](rust/contextcraft-ai-core/languages/rust/): Rust parsing, Cargo workspace discovery, and local module resolution.
- [`contextcraft-ai-core::languages::rust::dependencies`](rust/contextcraft-ai-core/languages/rust/dependencies/): Extract dependency references from captured syntax nodes.
- [`contextcraft-ai-core::languages::rust::manifest`](rust/contextcraft-ai-core/languages/rust/manifest/): Discover local package metadata and workspace relationships.
- [`contextcraft-ai-core::languages::rust::resolve`](rust/contextcraft-ai-core/languages/rust/resolve/): Resolve captured references to indexed local files.
- [`contextcraft-ai-core::languages::scala`](rust/contextcraft-ai-core/languages/scala/): Scala outlines, literal sbt projects, and local namespace imports.
- [`contextcraft-ai-core::languages::scala::manifest`](rust/contextcraft-ai-core/languages/scala/manifest/): Literal sbt project roots, dependsOn relationships, and build membership.
- [`contextcraft-ai-core::languages::scss`](rust/contextcraft-ai-core/languages/scss/): SCSS outlines and local Sass filesystem imports using the modern SCSS grammar.
- [`contextcraft-ai-core::languages::sql`](rust/contextcraft-ai-core/languages/sql/): PostgreSQL 18 schema and routine outlines using tree-sitter-postgres.
- [`contextcraft-ai-core::languages::svelte`](rust/contextcraft-ai-core/languages/svelte/): Svelte component markup, embedded script/style outlines, and local imports.
- [`contextcraft-ai-core::languages::swift`](rust/contextcraft-ai-core/languages/swift/): Swift outlines, local SwiftPM targets/products, and Xcode project/workspace metadata.
- [`contextcraft-ai-core::languages::swift::manifest`](rust/contextcraft-ai-core/languages/swift/manifest/): Static SwiftPM targets, products, and local package dependencies.
- [`contextcraft-ai-core::languages::swift::xcode`](rust/contextcraft-ai-core/languages/swift/xcode/): Static Xcode source membership, target dependencies, and workspace references.
- [`contextcraft-ai-core::languages::toml`](rust/contextcraft-ai-core/languages/toml/): TOML table, key, and scalar-value outlines.
- [`contextcraft-ai-core::languages::typescript`](rust/contextcraft-ai-core/languages/typescript/): TypeScript and TSX parsing with JavaScript package ownership.
- [`contextcraft-ai-core::languages::vue`](rust/contextcraft-ai-core/languages/vue/): Vue single-file components with embedded script/style outlines and local imports.
- [`contextcraft-ai-core::languages::yaml`](rust/contextcraft-ai-core/languages/yaml/): YAML key and scalar-value outlines.
- [`contextcraft-ai-core::languages::zig`](rust/contextcraft-ai-core/languages/zig/): Zig declaration outlines and literal file dependencies.
- [`contextcraft-ai-core::optimizer`](rust/contextcraft-ai-core/optimizer/): Select fidelity tiers using score-weighted utility per token.
- [`contextcraft-ai-core::package`](rust/contextcraft-ai-core/package/): Shared local package, dependency, and workspace metadata.
- [`contextcraft-ai-core::repo`](rust/contextcraft-ai-core/repo/): Read, redact, and analyze repository source files.
- [`contextcraft-ai-core::tiers`](rust/contextcraft-ai-core/tiers/): Render reusable fidelity tiers and lazily cache their framed token costs.
- [`contextcraft-ai-core::tokens`](rust/contextcraft-ai-core/tokens/): Count ordinary text tokens with the configured tokenizer vocabulary.
