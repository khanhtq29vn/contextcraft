---
title: "contextcraft-ai-core::languages::swift"
description: "Swift outlines, local SwiftPM targets/products, and Xcode project/workspace metadata."
editUrl: false
sidebar:
  order: 65
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Swift outlines, local SwiftPM targets/products, and Xcode project/workspace metadata.

Resolves module imports through explicit local target dependencies and source
membership. SwiftPM manifests are inspected, never executed. Dynamic manifests,
generated sources, remote package fetching, and compiler-level name binding are
not evaluated.

## Structs

### <span id="struct.Swift"></span><code style="font-size: 0.85em">struct Swift</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Swift grammar and local project analysis.
