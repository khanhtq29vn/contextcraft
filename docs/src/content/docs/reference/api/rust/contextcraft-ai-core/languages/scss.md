---
title: "contextcraft-ai-core::languages::scss"
description: "SCSS outlines and local Sass filesystem imports using the modern SCSS grammar."
editUrl: false
sidebar:
  order: 62
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

SCSS outlines and local Sass filesystem imports using the modern SCSS grammar.

Resolves `@use`, `@forward`, and legacy `@import` with Sass partial, extension,
index, and import-only precedence. Ambiguous matches, interpolation, built-ins,
configured load paths, and custom package importers are not inferred.

## Structs

### <span id="struct.Scss"></span><code style="font-size: 0.85em">struct Scss</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Scss structural outlines and static local imports.
