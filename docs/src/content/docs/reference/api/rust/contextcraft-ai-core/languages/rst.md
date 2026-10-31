---
title: "contextcraft-ai-core::languages::rst"
description: "reStructuredText outlines and literal local include dependencies."
editUrl: false
sidebar:
  order: 53
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

reStructuredText outlines and literal local include dependencies.

Relative `include` and Sphinx `literalinclude` paths are resolved against the
containing document. Sphinx toctrees and image/figure paths also produce edges.
Absolute paths, built-in includes, and URLs are not resolved.

## Structs

### <span id="struct.Rst"></span><code style="font-size: 0.85em">struct Rst</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

reStructuredText document outlines.
