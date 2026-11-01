---
title: "contextcraft-ai-core::languages::detect"
description: "Filename, extension, and content-based language detection."
editUrl: false
sidebar:
  order: 24
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Filename, extension, and content-based language detection.

## Enums

### <span id="enum.Evidence"></span><code style="font-size: 0.85em">enum Evidence</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Content evidence used to distinguish languages sharing an extension.

#### Variants

- **`Unknown`** - The source does not distinguish this language from other candidates.
- **`Supports`** - The source contains a distinguishing feature of this language.
- **`RulesOut`** - The source is incompatible with this language.
