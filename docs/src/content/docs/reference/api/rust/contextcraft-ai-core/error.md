---
title: "contextcraft-ai-core::error"
description: "Errors reported by repository analysis and artifact generation."
editUrl: false
sidebar:
  order: 7
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Errors reported by repository analysis and artifact generation.

## Enums

### <span id="enum.Error"></span><code style="font-size: 0.85em">enum Error</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Failures callers can distinguish when running individual pipeline stages.

#### Variants

- **`Io`** - A repository file or directory could not be accessed.
- **`NotADirectory`** - The requested repository root is not a directory.
- **`Ignore`** - Directory traversal or exclusion-pattern compilation failed.
- **`Query`** - A language query is invalid for its grammar.
- **`Language`** - The parser could not load a language grammar.
- **`Manifest`** - A package or workspace manifest is invalid.
- **`Parse`** - The parser did not produce a syntax tree.
- **`InvalidPipeline`** - Individually supplied pipeline inputs violate a consistency requirement.
- **`BudgetTooSmall`** - Output framing cannot fit within the requested token budget.
- **`Tokenization`** - The configured tokenizer is unavailable or could not count tokens.
