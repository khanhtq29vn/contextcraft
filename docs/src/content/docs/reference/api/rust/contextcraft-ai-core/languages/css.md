---
title: "contextcraft-ai-core::languages::css"
description: "CSS selector/declaration outlines and literal local stylesheet imports."
editUrl: false
sidebar:
  order: 22
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

CSS selector/declaration outlines and literal local stylesheet imports.

Quoted and `url(...)` imports resolve relative to the containing stylesheet.
Literal asset URLs also resolve locally. Remote URLs, browser-root paths,
and escaped or interpolated paths remain unresolved.

## Structs

### <span id="struct.Css"></span><code style="font-size: 0.85em">struct Css</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Css structural outlines and static local imports.
