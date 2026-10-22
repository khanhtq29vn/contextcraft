# Language Extension API

For supported formats and runnable custom-language examples, see
[Language Support](../language-supports.md).

## Registry

```{eval-rst}
.. autofunction:: contextcraft.default_registry
```

Returns a new registry containing the built-in language classes. Register your
own language before passing it to `ContextCraft(registry=registry)`.

```{eval-rst}
.. autoclass:: contextcraft.LanguageRegistry
   :members: register, get, detect_candidates, languages, ignore_patterns
   :undoc-members:
```

- `register()` accepts a `Language` subclass, not an instance. Duplicate IDs or
  aliases raise `ValueError`; multiple languages may share an extension.
- `get()` resolves an ID or alias, returning `None` for an unknown name.
- `detect_candidates()` prefers an exact, case-sensitive filename match over
  an extension match. Extensions are case-insensitive. Candidates retain
  registration order; an unknown path returns an empty list.
- `languages` is a tuple of registered classes. `ignore_patterns` combines
  their ignore patterns without duplicates.

```python
from contextcraft import default_registry

registry = default_registry()
python = registry.get("python")
assert python is not None
assert python in registry.detect_candidates("example.py")
```

## Language definition

The following types live in `contextcraft.languages.base`.

```{eval-rst}
.. autoclass:: contextcraft.languages.base.LanguageSpec
```

| Field | Meaning |
| :--- | :--- |
| `id` | Unique registry ID |
| `extensions` | Filename suffixes including the leading dot, such as `.py` |
| `filenames` | Exact filenames such as `Dockerfile` |
| `ignore_patterns` | Language-specific scanner exclusions |
| `parser_id` | Grammar name passed to tree-sitter-language-pack, or `None` |
| `aliases` | Additional names accepted by registry lookup |

```{eval-rst}
.. autoclass:: contextcraft.languages.base.Language
   :members: parse, build_scopes
   :undoc-members:
```

A subclass supplies four class attributes: `spec`, `extractor`,
`skeleton_builder`, and `signatures_builder`. The extractor and builders are
classes, not instances. `parse()` and `build_scopes()` delegate to a fresh
extractor instance.

## Extractors

```{eval-rst}
.. autoclass:: contextcraft.languages.base.ASTExtractor
   :members: extract, build_scopes
   :undoc-members:
```

This protocol accepts a tree-sitter root node and the original UTF-8 bytes.
`extract()` returns a `ParsedAst`; `build_scopes()` returns a `ScopeGraph`.

```{eval-rst}
.. autoclass:: contextcraft.languages.base.BaseExtractor
   :members: extract, build_scopes
   :undoc-members:
```

`BaseExtractor.extract()` creates a `ParsedAst` using `build_scopes()` and the
root's error status. Override `build_scopes()` at minimum; override `extract()`
to add symbols and imports.

```{eval-rst}
.. autofunction:: contextcraft.ast.parser.parse
```

This helper loads the configured grammar and calls the language extractor.
With `parser_id=None`, it returns a source-only AST. Grammar-loading failures
return a source-only AST with `has_errors=True`.

## Builders

```{eval-rst}
.. autoclass:: contextcraft.languages.base.SkeletonBuilder
   :members: build
   :undoc-members:
```

```{eval-rst}
.. autoclass:: contextcraft.languages.base.SignaturesBuilder
   :members: build
   :undoc-members:
```

Both builders receive a `LanguageSpec` at construction. Implement
`build(parsed)` to return text; token counting and tier fallback are handled by
`Elider`. Builders should use the supplied AST rather than reparsing the source.

## Scope data

These types live in `contextcraft.ast.scope`.

```{eval-rst}
.. autoclass:: contextcraft.ast.scope.ScopeGraph
```

`scopes`, `bindings`, and `references` hold the extracted lexical scope graph.

```{eval-rst}
.. autoclass:: contextcraft.ast.scope.Scope
   :members: resolve
   :undoc-members:
```

`resolve(name)` searches the current scope and then its parents, returning the
nearest `Binding` or `None`.

```{eval-rst}
.. autoclass:: contextcraft.ast.scope.Binding
```

```{eval-rst}
.. autoclass:: contextcraft.ast.scope.Reference
```

Bindings and references carry a name, half-open byte offsets, and their scope.
