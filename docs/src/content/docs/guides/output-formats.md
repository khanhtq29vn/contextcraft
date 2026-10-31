---
title: Choose an output format
description: Generate Markdown, XML, or JSON and control where the artifact is written.
---

ContextCraft counts the complete artifact against the budget in all three formats. Each format has a different framing cost, which can affect how much source detail fits.

## Markdown

```sh
contextcraft . --format markdown --budget 8k -o context.md
```

Markdown is the default. Saved and piped output preserves the original artifact content. When stdout is a terminal, the CLI renders Markdown with Rich.

## XML

```sh
contextcraft . --format xml --budget 8k -o context.xml
```

XML elements contain escaped paths and source content.

## JSON

```sh
contextcraft . --format json --budget 8k -o context.json
```

JSON contains a path listing and selected file blocks. For programmatic access to analysis data, the [Python SDK](../../python/quickstart/) also exposes the index, graph, scores, tiers, and artifact directly.

## Write to stdout

```sh
contextcraft . --format json --budget 8k --output -
```

Omitting `--output` also uses stdout. Summaries and diagnostics go to stderr, keeping piped artifact content separate. `--quiet` suppresses the summary, but not warnings.
