---
title: "contextcraft-ai-core::languages::bash"
description: "Bash `.sh` outlines and literal `source`/`.` dependencies."
editUrl: false
sidebar:
  order: 13
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Bash `.sh` outlines and literal `source`/`.` dependencies.

Source paths are resolved against the repository working directory. Runtime
expansions, PATH lookup, extensionless scripts, and shebang detection are not evaluated.

## Structs

### <span id="struct.Bash"></span><code style="font-size: 0.85em">struct Bash</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Bash grammar and local project analysis.
