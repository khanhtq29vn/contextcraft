# Language Support

ContextCraft registers **35 languages and formats** by default, with
language-specific parsing and summary builders.

## Supported languages and formats

Extensions are matched case-insensitively. Exact filenames are case-sensitive
and take precedence over extensions. Registry IDs are used in analysis results
and the Python API; they are not CLI flags.

### Programming languages

| Language         | Registry ID  | Extensions                                         | Exact filenames                    |
| :--------------- | :----------- | :------------------------------------------------- | :--------------------------------- |
| JavaScript / JSX | `javascript` | `.js`, `.mjs`, `.cjs`, `.jsx`                      |                                    |
| Python           | `python`     | `.py`, `.pyi`                                      |                                    |
| TypeScript       | `typescript` | `.ts`, `.cts`, `.mts`                              |                                    |
| TSX              | `tsx`        | `.tsx`                                             |                                    |
| Rust             | `rust`       | `.rs`                                              |                                    |
| Go               | `go`         | `.go`                                              |                                    |
| Java             | `java`       | `.java`                                            |                                    |
| C                | `c`          | `.c`, `.h`                                         |                                    |
| C++              | `cpp`        | `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`, `.hh`, `.hxx` |                                    |
| C#               | `csharp`     | `.cs`                                              |                                    |
| Ruby             | `ruby`       | `.rb`, `.rake`, `.gemspec`                         | `Gemfile`, `Rakefile`, `Guardfile` |
| PHP              | `php`        | `.php`, `.phtml`                                   |                                    |
| Swift            | `swift`      | `.swift`                                           |                                    |
| Kotlin           | `kotlin`     | `.kt`, `.kts`                                      |                                    |
| Scala            | `scala`      | `.scala`                                           |                                    |
| Lua              | `lua`        | `.lua`                                             |                                    |
| R                | `r`          | `.r`, `.R`                                         |                                    |
| Bash / shell     | `bash`       | `.sh`, `.bash`, `.zsh`                             |                                    |
| Elixir           | `elixir`     | `.ex`, `.exs`                                      |                                    |
| Zig              | `zig`        | `.zig`                                             |                                    |

### Structured data and markup

| Format | Registry ID | Extensions      | Exact filenames |
| :----- | :---------- | :-------------- | :-------------- |
| JSON   | `json`      | `.json`         |                 |
| YAML   | `yaml`      | `.yaml`, `.yml` |                 |
| TOML   | `toml`      | `.toml`         |                 |
| HTML   | `html`      | `.html`, `.htm` |                 |
| CSS    | `css`       | `.css`          |                 |
| SCSS   | `scss`      | `.scss`         |                 |

### Schemas and documents

| Format           | Registry ID | Extensions               | Exact filenames |
| :--------------- | :---------- | :----------------------- | :-------------- |
| SQL              | `sql`       | `.sql`                   |                 |
| Markdown         | `markdown`  | `.md`, `.mdx`            |                 |
| reStructuredText | `rst`       | `.rst`                   |                 |
| Protocol Buffers | `protobuf`  | `.proto`                 |                 |
| GraphQL          | `graphql`   | `.graphql`, `.gql`       |                 |
| HCL / Terraform  | `hcl`       | `.hcl`, `.tf`, `.tfvars` |                 |

### Build files

| Format     | Registry ID  | Extensions | Exact filenames                    |
| :--------- | :----------- | :--------- | :--------------------------------- |
| Dockerfile | `dockerfile` |            | `Dockerfile`, `dockerfile`         |
| Make       | `make`       |            | `Makefile`, `makefile`, `justfile` |
| CMake      | `cmake`      | `.cmake`   | `CMakeLists.txt`                   |

## Detection and fallback

ContextCraft checks the exact filename first, then the file extension. It does
not guess the language from the file's contents or shebang.

| Example file                   | What happens                                                                                                    |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| `src/app.JS`                   | Uses JavaScript. Extension matching ignores letter case.                                                        |
| `Dockerfile`                   | Uses the Dockerfile parser because the filename is registered.                                                  |
| `include/service.h`            | Tries C before C++, then uses the first parser that accepts the file without errors. If both accept it, C wins. |
| `notes.unknown`                | Uses `text` and keeps the source unchanged.                                                                     |
| `script` with a Python shebang | Uses `text`, unless that exact filename is registered.                                                          |

If no parser accepts a file, ContextCraft keeps the source rather than removing
code it cannot safely understand. The file is still labeled with its first
detected language. An unavailable grammar also causes source preservation,
unless another matching parser succeeds.

For example, a `.h` file that fails both C and C++ parsing is labeled `c`, but
its skeleton and signature tiers retain the source. Unknown files labeled
`text` do not need a parser at all.

"Unchanged source" means the **sanitized source** when secret redaction is on.

### Ignored files

Binary, empty, oversized, and ignored files are skipped before parsing. The
default registry also excludes common dependency directories, build artifacts,
caches, and lockfiles, such as `node_modules/`, `vendor/`, and `Cargo.lock`.
These exclusions apply across the repository, even if it contains no files of
the language that supplied the pattern.

`--no-gitignore` stops reading ignore files; it does not disable the registry's
built-in exclusions.

## Fidelity tiers

Every analyzed file has four candidate representations. The optimizer chooses
one under the output token budget.

| Tier   | Representation                                                            |
| :----- | :------------------------------------------------------------------------ |
| `FULL` | Complete sanitized source.                                                |
| `SKEL` | Language-specific structural skeleton, where safe elision is available.   |
| `SIGS` | Declaration summary or JSON name/kind outline, depending on the language. |
| `TREE` | Directory-tree entry without file content.                                |

### Skeleton behavior

- **Programming languages:** elide supported function and method bodies while
  retaining surrounding declarations, signatures, and supported documentation.
- **JSON, YAML, TOML:** replace eligible string values with placeholders while
  retaining the surrounding data structure.
- **HTML:** preserve tags, attributes, nesting, headings, and titles; elide
  text-only element contents and summarize supported embedded JavaScript/CSS.
- **CSS and SCSS:** elide eligible declaration blocks. Blocks containing custom
  properties, variables, or unsupported nested constructs are retained.
- **SQL, Markdown, reStructuredText, Protocol Buffers, GraphQL, HCL:** preserve
  source at the skeleton tier and provide structural outlines at `SIGS`.
- **Dockerfile, Make, CMake:** elide supported shell commands, recipes, or
  function/macro bodies while retaining their surrounding structure.

Programming-language signature summaries retain selected public declarations
and imports. Visibility handling is language-specific. Other formats use JSON
outlines containing symbol names and kinds.

Builders preserve source with syntax errors. If a summary is empty or costs
more tokens than the higher-fidelity representation, the elider reuses that
higher tier. Different tiers can therefore contain identical text.

## Inspecting and extending support

You can add languages from your own Python application. There is no need to
change ContextCraft's source code or create a particular directory layout.

### Inspect the available languages

```python
from contextcraft import default_registry

registry = default_registry()
for language in registry.languages:
    print(language.spec.id, sorted(language.spec.extensions))

print(registry.detect_candidates("service.h"))  # C, then C++
print(registry.get("proto").spec.id)  # protobuf
```

### Register a new extension or filename

If your files use an existing language's syntax, subclass that language and
provide a new `LanguageSpec`. The extractor and summary builders are inherited.

This example treats `.customjs` files and files named `Customfile` as JavaScript:

```python
from contextcraft import ContextCraft, default_registry
from contextcraft.languages.base import LanguageSpec
from contextcraft.languages.javascript.language import JavaScriptLanguage


class CustomJavaScript(JavaScriptLanguage):
    spec = LanguageSpec(
        id="custom-javascript",
        parser_id="javascript",
        extensions=frozenset({".customjs"}),
        filenames=frozenset({"Customfile"}),
        aliases=("custom-js",),
        ignore_patterns=(".customjs-cache/",),
    )


registry = default_registry()
registry.register(CustomJavaScript)
compiler = ContextCraft(registry=registry)
result = compiler.compile("./my-repo")
```

Each compiler gets a fresh default registry. Custom registration applies only to
the registry you pass in; the CLI does not load custom classes automatically.

To change an existing language's builders, replace its entry in a new registry
rather than appending another class for the same extension. Registration order
determines which parser is tried first.

For a new grammar, implement an extractor, skeleton builder, and signature
builder, then register a `Language` subclass. Use the built-in language packages
as examples and the [Language Extension API](api/languages.md) for the interfaces.
Builders should preserve source with syntax errors and avoid mutating the AST.
All source ranges are half-open UTF-8 byte offsets into the sanitized source.

See [Architecture](architecture.md) for the compilation pipeline and the
[API reference](api-reference.md) for SDK usage.
