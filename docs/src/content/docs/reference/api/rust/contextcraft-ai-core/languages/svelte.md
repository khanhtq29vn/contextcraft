---
title: "contextcraft-ai-core::languages::svelte"
description: "Svelte component markup, embedded script/style outlines, and local imports."
editUrl: false
sidebar:
  order: 64
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Svelte component markup, embedded script/style outlines, and local imports.

Supports JavaScript/TypeScript scripts, module scripts, Svelte 5 template
blocks, and CSS/SCSS styles. Components share npm/pnpm ownership and the static
JavaScript resolver. Preprocessors, auto-imports, generated aliases, and bundler
query modifiers are not inferred or executed.

## Structs

### <span id="struct.Svelte"></span><code style="font-size: 0.85em">struct Svelte</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Svelte grammar for `.svelte` single-file components.
