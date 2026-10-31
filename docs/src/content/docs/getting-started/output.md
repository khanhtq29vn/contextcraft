---
title: Understand the output
description: Read fidelity levels, token counts, and the generated context artifact.
---

ContextCraft produces an artifact containing selected repository context, with a different level of detail for each file.

## Four fidelity levels

| Level  | What it retains                                               |
| ------ | ------------------------------------------------------------- |
| `FULL` | Complete readable source after optional secret redaction.     |
| `SKEL` | A structural skeleton with implementation detail elided.      |
| `SIGS` | Signatures and declarations with less detail than a skeleton. |
| `TREE` | A path-only representation.                                   |

The exact skeleton and signatures depend on the [language implementation](../../reference/languages/). If a reduced representation is unavailable, the tier can fall back to richer content. A path in the artifact does not imply that its source was included. Some paths may also be omitted when the budget cannot accommodate the complete listing.

## Why files receive different levels

The pipeline ranks files using local dependencies and lexical relevance, then allocates detail according to utility per token. A focus query or focus path changes ranking without forcing a particular selection.

Oversized, binary, and non-UTF-8 files can remain indexed without a readable source entry. See [control scanned files](../../guides/files/).

## Read the token count

The final artifact count includes framing and path listings. The CLI’s source-token count measures source content directly, so it is not the same measurement.

The selected tokenizer vocabulary matters. Use the encoding appropriate to your workflow, and leave room for your own prompt and the response. See [choose a token budget](../../guides/token-budgets/).

## Choose a serialization

Markdown is the default. XML stores escaped paths and source content in elements, while JSON provides structured output. See [output formats](../../guides/output-formats/) for the CLI options.
