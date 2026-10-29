# Use a custom language

To use a language implementation from your own application, pass its class to
the SDK when creating a compiler. This requires no fork, edits to the
installed package, or global registration.

Custom implementations are available through the SDK rather than the CLI,
which does not discover Python plugins or load language classes.

## Add a Tree-sitter-backed Rust outline

The example below uses Tree-sitter to recognize top-level Rust functions,
keeping their headers at `SIGS` and adding adjacent `///` documentation with
bodies replaced by `{ ... }` at `SKEL`. The original source remains available
at `FULL`.

Declare the dependencies in your application's project:

```bash
uv add contextcraft-ai tree-sitter tree-sitter-rust
```

For example, save this source as `src/lib.rs` in the repository you want to
analyze:

```rust
/// Add two values.
pub fn add(left: i32, right: i32) -> i32 {
    left + right
}
```

Put the implementation below in a module you own, or use it directly in your
application:

```python
from __future__ import annotations

import tree_sitter as ts
import tree_sitter_rust

from contextcraft import ContextCraft
from contextcraft.config import Config
from contextcraft.languages import BUILTIN_LANGUAGES
from contextcraft.languages.base import Language
from contextcraft.models import File, FileAnalysis, Import, ImportResolution, ModuleRoot

RUST_GRAMMAR = ts.Language(tree_sitter_rust.language())
DOC_QUERY = ts.Query(RUST_GRAMMAR, "(line_comment doc: (doc_comment) @doc)")


class RustOutlineLanguage(Language):
    @staticmethod
    def get_language_id() -> str:
        return "rust-outline"

    @staticmethod
    def get_file_extensions() -> frozenset[str]:
        return frozenset({".rs"})

    @staticmethod
    def get_filenames() -> frozenset[str]:
        return frozenset()

    @staticmethod
    def get_root_files() -> frozenset[str]:
        return frozenset({"Cargo.toml"})

    @staticmethod
    def get_package_files() -> frozenset[str]:
        return frozenset({"Cargo.toml", "Cargo.lock"})

    @staticmethod
    def get_ignore_patterns() -> tuple[str, ...]:
        return ("**/target/**", "**/Cargo.lock")

    @staticmethod
    def analyze(source: bytes, file_id: int) -> FileAnalysis:
        tree = ts.Parser(RUST_GRAMMAR).parse(source)
        captures = ts.QueryCursor(DOC_QUERY).captures(tree.root_node)
        docstrings = tuple(
            source[node.start_byte : node.end_byte].decode("utf-8").strip()
            for node in sorted(
                captures.get("doc", []), key=lambda node: node.start_byte
            )
        )

        if tree.root_node.has_error:
            full = ((0, len(source), 0),)
            return FileAnalysis(docstrings=docstrings, imports=(), sigs=full, skel=full)

        signatures = set()
        skeleton = set()

        for node in tree.root_node.named_children:
            if node.type != "function_item":
                continue

            body = node.child_by_field_name("body")
            if body is None:
                continue

            header = source[node.start_byte : body.start_byte].rstrip()
            span = (node.start_byte, node.start_byte + len(header), 0)
            signatures.add(span)
            skeleton.add(span)
            previous = node.prev_named_sibling

            while previous is not None and previous.type == "line_comment":
                text = source[previous.start_byte : previous.end_byte].rstrip()
                if not text.startswith(b"///") or text.startswith(b"////"):
                    break
                skeleton.add((previous.start_byte, previous.start_byte + len(text), 0))
                previous = previous.prev_named_sibling

        return FileAnalysis(
            docstrings=docstrings,
            imports=(),
            sigs=tuple(sorted(signatures)),
            skel=tuple(sorted(skeleton)),
        )

    @staticmethod
    def resolve_imports(
        files: dict[int, File],
        modules: dict[int, ModuleRoot],
        imports: dict[int, Import],
    ) -> list[ImportResolution]:
        return []

    @staticmethod
    def render_skel(source: bytes, analysis: FileAnalysis) -> str:
        if analysis.skel == ((0, len(source), 0),):
            return source.decode("utf-8")

        headers = set(analysis.sigs)
        parts = []

        for span in analysis.skel:
            start, end, column = span
            text = (b" " * column + source[start:end]).decode("utf-8")
            parts.append(text + " { ... }" if span in headers else text)

        return "\n".join(parts)


compiler = ContextCraft(
    Config(budget_tokens=8000),
    languages=(*BUILTIN_LANGUAGES, RustOutlineLanguage),
)
artifact = compiler.compile(".")
```

`analyze()` parses once and stores byte spans. The class inherits the default
`render_sigs(source, analysis)` method and overrides only skeleton formatting
to add body placeholders. Neither renderer parses or queries again.

For the sample function, `SIGS` returns:

```rust
pub fn add(left: i32, right: i32) -> i32
```

`SKEL` returns:

```rust
/// Add two values.
pub fn add(left: i32, right: i32) -> i32 { ... }
```

By slicing source bytes at Tree-sitter's offsets rather than splitting
declarations by line, the example preserves multiline headers and Unicode in
its outlines, although the result is not necessarily valid Rust. If parsing
fails, both renderers return the original source instead.

The example is intentionally limited to top-level functions, omitting structs,
enums, traits, methods, nested modules, and attributes. It retains `///`
comments only when they directly precede a function among its named siblings,
so block documentation and comments separated by attributes are not included.

Import extraction and resolution are also left unimplemented. As a result,
`use` and `mod` declarations create no dependency edges, and Rust files are
ranked without those relationships.

## Choose which languages to use

Because the `languages` tuple replaces the defaults, the example expands
`BUILTIN_LANGUAGES` before appending the new class under its own
`rust-outline` ID. If you only want Rust outline analysis, pass
`languages=(RustOutlineLanguage,)`, which still allows other files to be
loaded as text.

Give each implementation a distinct ID and order the tuple deliberately, since
detection selects the first class matching the case-sensitive suffix or exact
filename. When replacing a built-in, omit the original rather than supplying
two implementations with the same ID.

Your analysis methods receive UTF-8 bytes after any enabled redaction, while
`TierRenderer` handles token counting and reuses the next richer tier if an
outline is empty or larger. Budget enforcement remains the pipeline's
responsibility, not the language implementation's.

## Check your application's output

Compile a small directory of representative files and read the artifact to
check its declarations, retained documentation, and selected tiers. For a
closer look at detection or imports, run the [pipeline
stages](../reference/api/stages.md) with your language tuple supplied to
`Indexer`.

Once indexing records the detected classes in `index.languages`, loading,
resolution, ranking, and rendering reuse that mapping without separate
language lists. Consult the [language interface](../reference/api/language.md)
for the full contract, including import records for languages that need them.

Using an implementation privately does not require contributing it upstream.
If you want it included in ContextCraft's built-ins, follow [Contribute a
language](../contributing/adding-a-language.md).
