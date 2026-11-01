---
title: "contextcraft-ai-core::languages::r"
description: "R function outlines, literal source calls, and static local package namespaces."
editUrl: false
sidebar:
  order: 59
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

R function outlines, literal source calls, and static local package namespaces.

DESCRIPTION and NAMESPACE restrict package visibility and exported symbols.
Computed paths, nonstandard evaluation, runtime search paths, and package installation
are not evaluated. R Markdown and Quarto documents are not parsed as R source.

## Structs

### <span id="struct.R"></span><code style="font-size: 0.85em">struct R</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

R grammar for source files and NAMESPACE declarations.
