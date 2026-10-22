# Language Support

ContextCraft registers **33 languages and formats** by default, with
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

`default_registry()` returns a fresh registry containing the built-in languages.
Registering your class adds support to that registry; it does not modify other
compiler instances or the installed package.

The specification controls:

- **`id`:** the language name reported in analysis results. It must be unique.
- **`parser_id`:** the grammar name passed to `tree-sitter-language-pack`. The
  custom ID does not need to match it. Registration does not install a grammar.
- **`extensions`:** extensions including the leading dot, such as `.customjs`.
  Detection uses the final suffix, so `.custom.js` still matches `.js`.
- **`filenames`:** exact basenames, without directory paths.
- **`aliases`:** additional names for `registry.get()`, not extra filename rules.
  Aliases must also be unique.
- **`ignore_patterns`:** repository-wide exclusions contributed by your language.

Pass the registry to `ContextCraft(registry=registry)` to use it for both
`compile()` and `analyze_repository()`. Custom registration is a Python API
feature; the stock CLI does not load these classes automatically.

### Customize summaries for an existing language

You can replace either summary builder while reusing the existing parser and
extractor. Builders receive the language specification in their constructor
and a `ParsedAst` in `build()`. The AST contains sanitized source bytes; use
`parsed.text(range)` to read a symbol's source span.

This complete example changes the JavaScript signature tier to include only
public, top-level function headers:

```python
from dataclasses import replace

from contextcraft import ContextCraft, LanguageRegistry, default_registry
from contextcraft.ast import ParsedAst
from contextcraft.languages.base import SignaturesBuilder
from contextcraft.languages.javascript.language import JavaScriptLanguage


class CustomSignaturesBuilder(SignaturesBuilder):
    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        headers = [
            parsed.text(symbol.signature_range)
            for symbol in parsed.symbols
            if symbol.kind == "function" and symbol.is_public and symbol.parent is None
        ]
        return "\n".join(headers) + "\n" if headers else ""


class ProjectJavaScript(JavaScriptLanguage):
    spec = replace(JavaScriptLanguage.spec, id="project-javascript")
    signatures_builder = CustomSignaturesBuilder


registry = LanguageRegistry()
for language in default_registry().languages:
    registry.register(ProjectJavaScript if language is JavaScriptLanguage else language)

compiler = ContextCraft(registry=registry)
result = compiler.compile("./my-repo")
```

The replacement registry above keeps the other built-in languages, but registers
`ProjectJavaScript` **instead of** the built-in JavaScript class. Simply adding
another class for `.js` to the default registry would leave the built-in parser
first in line, so your custom builder would normally not be selected.

Use the same approach with a `SkeletonBuilder` subclass and `skeleton_builder`
to change the skeleton tier. Builders should return text without modifying the
AST. Preserve the source when it has syntax errors. Returning an empty summary,
or one that costs more tokens than the higher tier, makes the elider reuse that
higher tier instead. The optimizer still decides which tier reaches the output;
a custom signature builder is used when `SIGS` is selected.

### Write your own extractor and builders

This example adds INI support from your own application. It uses the `ini`
Tree-sitter grammar and implements its own extraction and summaries.

Given this file:

```ini
[database]
host = database.internal.example-company.local
password = example-long-password-for-local-development-only
```

The extractor records each section as a parent symbol and each setting as a
child. A setting's key becomes its signature range, and its value becomes the
range that the skeleton builder replaces. `build_scopes()` supplies a file-level
scope; section relationships are represented by the symbols' `parent` links.

The complete example below creates a sample repository, registers the language,
and prints both summary tiers:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from tree_sitter import Node

from contextcraft import ContextCraft, FidelityLevel, default_registry
from contextcraft.ast import ByteRange, ParsedAst, Symbol
from contextcraft.ast.scope import Scope, ScopeGraph
from contextcraft.languages.base import (
    BaseExtractor,
    Language,
    LanguageSpec,
    SignaturesBuilder,
    SkeletonBuilder,
)


def span(node: Node) -> ByteRange:
    return ByteRange(node.start_byte, node.end_byte)


class CustomExtractor(BaseExtractor):
    def build_scopes(self, root: Node, source: bytes) -> ScopeGraph:
        return ScopeGraph(scopes=[Scope(0, len(source), kind="module")])

    def extract(self, root: Node, source: bytes) -> ParsedAst:
        parsed = super().extract(root, source)
        if parsed.has_errors:
            return parsed

        for section in root.named_children:
            if section.type != "section":
                continue
            header = next(child for child in section.named_children if child.type == "section_name")
            header_text = parsed.text(span(header)).strip()
            parent = Symbol(
                name=header_text[1:-1].strip(),
                kind="section",
                declaration_range=span(section),
                signature_range=span(header),
            )
            parsed.symbols.append(parent)

            for setting in section.named_children:
                if setting.type != "setting":
                    continue
                key = next(
                    child for child in setting.named_children if child.type == "setting_name"
                )
                value = next(
                    (child for child in setting.named_children if child.type == "setting_value"),
                    None,
                )
                value_range = None
                if value is not None:
                    raw = source[value.start_byte : value.end_byte]
                    start = value.start_byte + len(raw) - len(raw.lstrip(b" \t"))
                    value_range = ByteRange(start, value.end_byte)

                parsed.symbols.append(
                    Symbol(
                        name=parsed.text(span(key)).strip(),
                        kind="setting",
                        declaration_range=span(setting),
                        signature_range=span(key),
                        body_range=value_range,
                        parent=parent,
                    )
                )
        return parsed


class CustomSkeletonBuilder(SkeletonBuilder):
    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        ranges = sorted(
            (symbol.body_range for symbol in parsed.symbols if symbol.body_range is not None),
            key=lambda value: value.start_byte,
            reverse=True,
        )
        source = bytearray(parsed.source)
        for value in ranges:
            source[value.start_byte : value.end_byte] = b'"<elided>"'
        return source.decode("utf-8")


class CustomSignaturesBuilder(SignaturesBuilder):
    def build(self, parsed: ParsedAst) -> str:
        if parsed.has_errors:
            return parsed.source.decode("utf-8")

        lines = [parsed.text(symbol.signature_range).strip() for symbol in parsed.symbols]
        return "\n".join(lines) + "\n" if lines else ""


class CustomIni(Language):
    spec = LanguageSpec(
        id="custom-ini",
        parser_id="ini",
        extensions=frozenset({".ini"}),
    )
    extractor = CustomExtractor
    skeleton_builder = CustomSkeletonBuilder
    signatures_builder = CustomSignaturesBuilder


registry = default_registry()
registry.register(CustomIni)
compiler = ContextCraft(registry=registry)

with TemporaryDirectory() as directory:
    sample = Path(directory) / "settings.ini"
    sample.write_text(
        "[database]\nhost = database.internal.example-company.local\npassword = example-long-password-for-local-development-only\n",
        encoding="utf-8",
    )
    file = compiler.analyze_repository(directory)[0]
    print(file.tiers[FidelityLevel.SKELETON].content)
    print(file.tiers[FidelityLevel.SIGNATURES].content)
    result = compiler.compile(directory)
```

Skeleton output:

```ini
[database]
host = "<elided>"
password = "<elided>"
```

Signature output:

```text
[database]
host
password
```

All ranges use UTF-8 byte offsets into `ParsedAst.source`. The skeleton builder
edits from the end of the file backward so replacing one value does not shift
the ranges of earlier values. Neither builder modifies the original AST.

For your own grammar, change `parser_id` to its available
`tree-sitter-language-pack` name and adapt the extractor to that grammar's node
types. Populate `ParsedAst.imports` and `ScopeGraph` bindings/references when your
language has dependencies or names you want included in repository analysis.

Use `LanguageRegistry()` without built-ins if you want only your own detection
rules; other files will use the `text` fallback. A `parser_id` of `None` also
preserves text and bypasses the extractor, so it is not a way to register a
custom parsing function.

See [Architecture](architecture.md) and the [API reference](api-reference.md)
for pipeline and SDK details.
