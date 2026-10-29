# Results and pipeline models

The types in `contextcraft.models` are keyword-only, frozen `msgspec.Struct`
records apart from the `FidelityLevel` enum. Their fields cannot be
reassigned, although the dictionaries held inside the records remain mutable.

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

`selected_tiers` reflects any downgrades made during formatting rather than
just the initial allocation. The artifact does not retain the index or
per-file scores, so run the pipeline stages individually if you need those
records.

The output count is exact for the configured tokenizer when
`token_counts_estimated` is false, and approximate when it is true. Only exact
counts support the exact-budget guarantee.

## Fidelity and rendered tiers

```{eval-rst}
.. autoclass:: contextcraft.models.FidelityLevel
   :members: TREE, SIGS, SKEL, FULL, semantic_utility
```

| Level  | Value | Utility | Content                                                      |
| :----- | :---- | :------ | :----------------------------------------------------------- |
| `TREE` | `0`   | `0.0`   | No file content. Its path may appear in the budgeted listing |
| `SIGS` | `1`   | `0.45`  | Declaration outline                                          |
| `SKEL` | `2`   | `0.82`  | Declaration outline with retained documentation              |
| `FULL` | `3`   | `1.0`   | Full loaded source after optional redaction                  |

Allocation uses these utilities to weight tier upgrades, while the language
implementation determines the content of each outline, which does not need to
be executable source.

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
- `analyses`: file IDs mapped to `FileAnalysis` records containing metadata and
  sorted, deduplicated `SIGS` and `SKEL` spans.

Each span is `(start_byte, end_byte, indentation)` into the analyzed UTF-8
bytes. Ranking and tier rendering slice those bytes without parsing or querying
again. They do not cache rendered outlines. Manually created `Source` records
must include an analysis for every loaded file with a detected language.

Files rejected for size, binary control bytes, or invalid UTF-8 remain in the
index without a `content` entry. For eligible files, any enabled redaction
masks source bytes before metadata extraction while preserving byte offsets
and line endings, but does not return secret-match metadata.

## Imports and resolutions

```{eval-rst}
.. autoclass:: contextcraft.models.Import

.. autoclass:: contextcraft.models.ImportResolution
```

| Record             | Field                | Meaning                                                                 |
| :----------------- | :------------------- | :---------------------------------------------------------------------- |
| `Import`           | `source_file_id`     | ID of the importing file in `Index.files`                               |
| `Import`           | `module_name`        | Imported module name without leading relative dots                      |
| `Import`           | `relative_level`     | Number of leading relative-import dots, or zero for an absolute import  |
| `Import`           | `imported_names`     | Names requested by a from-import, with `("*",)` representing a wildcard |
| `ImportResolution` | `import_id`          | Position of the import in `Source.imports`                              |
| `ImportResolution` | `target_file_ids`    | Definite target file IDs                                                |
| `ImportResolution` | `ambiguous_file_ids` | Candidate file IDs that could not be resolved uniquely                  |
| `ImportResolution` | `unresolved_names`   | Names that were not resolved to indexed files                           |

A resolution can include definite targets alongside unresolved names, since an
unresolved name may refer to an external dependency or attribute rather than a
missing file. The dependency graph uses only the definite targets, omitting
self-imports and merging repeated edges between the same files.
