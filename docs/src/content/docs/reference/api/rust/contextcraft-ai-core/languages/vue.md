---
title: "contextcraft-ai-core::languages::vue"
description: "Vue single-file components with embedded script/style outlines and local imports."
editUrl: false
sidebar:
  order: 70
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Vue single-file components with embedded script/style outlines and local imports.

Supports JavaScript, TypeScript, TSX, CSS, and SCSS blocks, including script
setup and compiler-macro contracts. Components share npm/pnpm ownership and
the existing static JavaScript resolver. Template preprocessors, auto-imports,
and bundler-specific aliases or query modifiers are not inferred or executed.

## Structs

### <span id="struct.Vue"></span><code style="font-size: 0.85em">struct Vue</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Vue grammar for `.vue` single-file components.
