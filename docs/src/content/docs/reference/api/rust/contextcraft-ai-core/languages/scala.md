---
title: "contextcraft-ai-core::languages::scala"
description: "Scala outlines, literal sbt projects, and local namespace imports."
editUrl: false
sidebar:
  order: 60
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Scala outlines, literal sbt projects, and local namespace imports.

Supports Scala 2/3 outlines, sbt `project`/`Project` declarations, literal source
directories, and `dependsOn`. Aggregation records membership, not dependencies.
Arbitrary sbt code, plugins, Mill/Gradle builds, and compiler-level symbol binding
are not evaluated.

## Structs

### <span id="struct.Scala"></span><code style="font-size: 0.85em">struct Scala</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Scala grammar and local project analysis.
