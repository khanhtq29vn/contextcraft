---
title: Language support
description: Supported file types, syntax outlines, local dependencies, and package discovery.
---

ContextCraft uses Tree-sitter to parse the languages and formats below. Each has syntax-based `SIGS` and `SKEL` outlines, but the retained content varies by language. Parsing support does not imply compiler-level name resolution or support for every build system.

## Programming languages and components

The dependency column describes relationships that can contribute edges to file ranking. Resolution is limited to indexed local files and the static constructs recognized by each implementation.

| Language           | Recognized extensions                                                                            | Local dependency analysis                                                    |
| :----------------- | :----------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------- |
| Bash               | `.sh`                                                                                            | Literal `source` and `.` paths, relative to the repository root              |
| C                  | `.c`, `.h`                                                                                       | Local includes and literal include paths from `compile_commands.json`        |
| C++                | `.cpp`, `.cc`, `.cxx`, `.c++`, `.C`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.H`, `.ipp`, `.tpp`, `.inl` | Uses the C include resolver                                                  |
| C#                 | `.cs`                                                                                            | Namespace and type imports within visible local projects                     |
| Elixir             | `.ex`, `.exs`                                                                                    | Captured module references within visible local Mix applications             |
| Go                 | `.go`                                                                                            | Local imports with module and workspace metadata                             |
| JavaScript and JSX | `.js`, `.jsx`, `.mjs`, `.cjs`                                                                    | Static module references and local workspace packages                        |
| Kotlin             | `.kt`, `.kts`                                                                                    | Package-qualified imports within visible local Gradle projects               |
| Lua                | `.lua`                                                                                           | Literal module references and local LuaRocks module mappings                 |
| Python             | `.py`, `.pyi`, `.pyw`                                                                            | Local absolute and relative imports, with package source roots               |
| Ruby               | `.rb`                                                                                            | Literal `require` and `require_relative`, with local load paths              |
| Rust               | `.rs`                                                                                            | Local modules and imports, with Cargo target and dependency visibility       |
| Scala              | `.scala`, `.sc`                                                                                  | Namespace imports within visible local sbt projects                          |
| Svelte             | `.svelte`                                                                                        | Supported embedded script imports and local assets                           |
| Swift              | `.swift`                                                                                         | Module imports through local SwiftPM and Xcode dependencies                  |
| TypeScript         | `.ts`, `.mts`, `.cts`                                                                            | JavaScript module resolution with supported TypeScript configuration aliases |
| TSX                | `.tsx`                                                                                           | TypeScript module resolution with JSX syntax                                 |
| Vue                | `.vue`                                                                                           | Supported embedded script imports and local assets                           |
| Zig                | `.zig`                                                                                           | Literal file paths in `@import` and `@embedFile`                             |

Extensions are case-sensitive. Conventional filenames are checked before extensions. Files ending in `.h` are parsed as C or C++ to detect C++ constructs, with C as the fallback.

Vue and Svelte can analyze supported JavaScript, TypeScript, TSX, CSS, and SCSS sections. This does not evaluate component code or resolve every framework convention.

## Data, markup, and build files

These formats also have syntax-based outlines. For data files, outlines retain keys and structure rather than function declarations. Some formats contribute file dependencies without defining packages of their own.

| Language or format           | Recognized files                                                                            | Local dependency analysis                                                                  |
| :--------------------------- | :------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------- |
| CMake                        | `.cmake`, `CMakeLists.txt`                                                                  | Supported static includes, subdirectories, target sources, and target references           |
| CSS                          | `.css`                                                                                      | Literal local imports and URL references                                                   |
| Dockerfile and Containerfile | `Dockerfile`, `Containerfile`, their dotted variants, `.dockerfile`, `.containerfile`       | Local `COPY` and `ADD` sources for root-level build files, subject to Docker ignore rules  |
| GraphQL                      | `.graphql`, `.gql`, `.graphqls`                                                             | Explicit local imports and fragment references within imported or configured document sets |
| HCL and Terraform            | `.hcl`, `.tf`, `.tfvars`                                                                    | Local Terraform module sources and unambiguous references between `.tf` files              |
| HTML                         | `.html`, `.htm`                                                                             | Local assets, with supported inline JavaScript and CSS analysis                            |
| JSON                         | `.json`                                                                                     | None                                                                                       |
| Just                         | `.just`, `justfile`, `.justfile`                                                            | Explicit imports, modules, and named recipe dependencies                                   |
| Make                         | `.mk`, `.mak`, `.make`, `Makefile`, `makefile`, `GNUmakefile`, `Makefile.am`, `Makefile.in` | Literal includes and supported source or target prerequisites                              |
| Markdown                     | `.md`, `.markdown`, `.mdown`, `.mkd`, `.mkdn`                                               | Literal local links and assets                                                             |
| Protocol Buffers             | `.proto`                                                                                    | Local imports using repository or declared Buf module roots                                |
| reStructuredText             | `.rst`, `.rest`                                                                             | Supported local includes and toctree entries                                               |
| SCSS                         | `.scss`                                                                                     | Local `@use`, `@forward`, and `@import`, including Sass partial and index lookup           |
| SQL                          | `.sql`                                                                                      | None. Outlines use a PostgreSQL grammar, not automatic dialect detection                   |
| TOML                         | `.toml`                                                                                     | None                                                                                       |
| YAML                         | `.yaml`, `.yml`                                                                             | None                                                                                       |

Just recognizes `justfile` and `.justfile` without regard to case. Dockerfile and Containerfile dotted variants include names such as `Dockerfile.dev`, but not `.dockerignore` files.

## Package and workspace discovery

Package discovery determines source ownership and which local projects can see one another. It is separate from parsing. For example, a `package.json` file is parsed as JSON while its metadata defines a JavaScript package.

| Ecosystem  | Package or project metadata                                                  | Supported local relationships                                           |
| :--------- | :--------------------------------------------------------------------------- | :---------------------------------------------------------------------- |
| Python     | `pyproject.toml`, packaging `setup.py`, `setup.cfg`                          | Source roots, uv workspaces, and explicit local dependencies            |
| Rust       | `Cargo.toml`                                                                 | Cargo workspaces, targets, and local dependencies                       |
| Go         | `go.mod`, `go.work`                                                          | Local modules, workspace membership, and replacements                   |
| JavaScript | `package.json`, `pnpm-workspace.yaml`                                        | Local npm and pnpm packages and workspaces                              |
| C#         | `.csproj`, `.sln`, `.slnx`                                                   | Static source membership, project references, and solutions             |
| Elixir     | `mix.exs`                                                                    | Literal application names, path dependencies, and umbrella membership   |
| Kotlin     | `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts` | Literal project includes, directory mappings, and project dependencies  |
| Lua        | `.rockspec`                                                                  | Literal package names and declared local rock dependencies              |
| Ruby       | `Gemfile`, `.gemspec`                                                        | Literal gem names, local path dependencies, and declared load paths     |
| Scala      | `build.sbt`                                                                  | Literal sbt projects, source directories, and `dependsOn` relationships |
| Swift      | `Package.swift`, Xcode project and workspace metadata                        | Local targets, products, source membership, and project dependencies    |
| Terraform  | Directories containing `.tf` files                                           | Directory modules and literal local module sources                      |
| Zig        | `build.zig`                                                                  | Package boundary only, without evaluating build dependencies            |

TypeScript, TSX, Vue, and Svelte share JavaScript package ownership. C++ shares C package ownership, but neither currently discovers a package graph from CMake or Make files. Those files can still contribute their own file-level dependencies.

Build files are inspected rather than executed. Computed paths, arbitrary build logic, generated sources, remote package fetching, and compiler-level type binding are outside this static analysis. An unrecognized or ambiguous reference may therefore produce no dependency edge.

## Missing or unsupported syntax

A readable UTF-8 file without a matching parser can still appear as full source. Its reduced tiers reuse that source. Files skipped because of size, binary content, or invalid UTF-8 remain available as paths only.

For a recognized language, an empty outline can produce an outline-unavailable placeholder rather than useful reduced source. Check the artifact and use a larger budget when full source is needed. Syntax outlines need not be executable programs.

For details, see [fidelity levels](../../getting-started/output/), [file scanning](../../guides/files/), and the [language API](../api/rust/contextcraft-ai-core/languages/).
