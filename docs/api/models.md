# Results and Pipeline Models

Import these types from `contextcraft.models`. They are keyword-only, frozen
`msgspec.Struct` records, except for the `FidelityLevel` enum. Frozen records
prevent field reassignment; their nested dictionaries remain mutable.

## Artifact

```{eval-rst}
.. autoclass:: contextcraft.models.Artifact
```

`ContextCraft.compile()` returns an `Artifact` with these fields:

| Field                    | Meaning                                                                    |
| :----------------------- | :------------------------------------------------------------------------- |
| `content`                | Complete Markdown, XML, or JSON output                                     |
| `tokens`                 | Token count of the complete output, including framing and the path listing |
| `token_counts_estimated` | Whether any pipeline token count used an estimate                          |
| `selected_tiers`         | Final fidelity level for every indexed file ID                             |

`selected_tiers` includes any downgrades made during formatting. The artifact
does not contain the index or per-file scores; use the individual pipeline
stages to retain those records.

If `token_counts_estimated` is false, the output count is exact for the configured
tokenizer. If true, the count is approximate and the exact-budget guarantee does
not apply.

## Fidelity and rendered tiers

```{eval-rst}
.. autoclass:: contextcraft.models.FidelityLevel
   :members: TREE, SIGS, SKEL, FULL, semantic_utility
```

| Level  | Value | Utility | Content                                                      |
| :----- | :---- | :------ | :----------------------------------------------------------- |
| `TREE` | `0`   | `0.0`   | No file content; its path may appear in the budgeted listing |
| `SIGS` | `1`   | `0.45`  | Declaration outline                                          |
| `SKEL` | `2`   | `0.82`  | Declaration outline with retained documentation              |
| `FULL` | `3`   | `1.0`   | Full loaded source after optional redaction                  |

Utilities weight tier upgrades during allocation. Rendered content depends on
the language implementation; an outline need not be executable source.

```{eval-rst}
.. autoclass:: contextcraft.models.RenderedTier

.. autoclass:: contextcraft.models.Tiers

.. autoclass:: contextcraft.models.Selection
```

- `RenderedTier.content` is file text. `tokens` counts that text without output
  framing.
- `Tiers.files` maps each file ID to its available `FidelityLevel` and
  `RenderedTier` pairs. Every indexed file has a zero-content, zero-token `TREE`
  tier. Files rejected during loading have no higher tiers.
- `Selection.tiers` maps file IDs to the levels chosen by the allocator, before
  the formatter's final budget check.
- `Tiers.token_counts_estimated` and `Selection.token_counts_estimated` record
  whether token counting used an estimate.

For loaded files without a detected language, `SIGS` and `SKEL` reuse full
source. Empty compressed renderings, or renderings larger than the next richer
tier, also reuse that richer tier.

## Index and files

```{eval-rst}
.. py:class:: contextcraft.models.Index(*, path: pathlib.Path, languages=..., modules=..., files=..., focus_file_ids=frozenset())

   Store repository files, project roots, detected language implementations,
   and focus matches. Mapping fields default to new empty dictionaries.

.. autoclass:: contextcraft.models.ModuleRoot

.. autoclass:: contextcraft.models.File
```

| Record       | Field            | Meaning                                                      |
| :----------- | :--------------- | :----------------------------------------------------------- |
| `Index`      | `path`           | Resolved repository root as a `Path`                         |
| `Index`      | `languages`      | Detected language IDs mapped to their implementation classes |
| `Index`      | `modules`        | Module IDs mapped to `ModuleRoot` records                    |
| `Index`      | `files`          | File IDs mapped to `File` records                            |
| `Index`      | `focus_file_ids` | Frozen set of file IDs matched by focus patterns             |
| `ModuleRoot` | `path`           | Absolute project-root path                                   |
| `File`       | `path`           | Absolute source-file path                                    |
| `File`       | `module_id`      | ID of the nearest owning project root                        |
| `File`       | `language_id`    | Detected language ID, or `None` for an unrecognized file     |

File and module IDs belong to one index and must not be mixed across analyses.
`Index.languages` contains only implementations detected among indexed files.
Later language-dependent stages require this mapping for non-null language IDs.

## Loaded source

```{eval-rst}
.. autoclass:: contextcraft.models.Source
```

`Source` contains:

- `content`: file IDs mapped to loaded UTF-8 bytes.
- `docstrings`: file IDs mapped to tuples of extracted docstring values.
- `imports`: a tuple of structured import records.

Files that exceed the configured size limit, contain binary control bytes, or
cannot be decoded as UTF-8 have no `content` entry. They remain in the index.
When redaction is enabled, loaded bytes are masked before metadata extraction;
masking preserves byte offsets and line endings. No secret-match metadata is
returned.

## Imports and resolutions

```{eval-rst}
.. autoclass:: contextcraft.models.Import

.. autoclass:: contextcraft.models.ImportResolution
```

| Record             | Field                | Meaning                                                           |
| :----------------- | :------------------- | :---------------------------------------------------------------- |
| `Import`           | `source_file_id`     | ID of the importing file in `Index.files`                         |
| `Import`           | `module_name`        | Imported module name without leading relative dots                |
| `Import`           | `relative_level`     | Number of leading relative-import dots; zero for absolute imports |
| `Import`           | `imported_names`     | Names requested by a from-import; `("*",)` for a wildcard         |
| `ImportResolution` | `import_id`          | Position of the import in `Source.imports`                        |
| `ImportResolution` | `target_file_ids`    | Definite target file IDs                                          |
| `ImportResolution` | `ambiguous_file_ids` | Candidate file IDs that could not be resolved uniquely            |
| `ImportResolution` | `unresolved_names`   | Names that were not resolved to indexed files                     |

A resolution may include both definite targets and unresolved names. An
unresolved name can refer to an external dependency or an attribute rather than
a missing file. The dependency graph uses only definite targets; it omits
self-imports and merges repeated edges between the same files.
