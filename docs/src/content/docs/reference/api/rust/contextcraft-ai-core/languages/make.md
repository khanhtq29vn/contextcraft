---
title: "contextcraft-ai-core::languages::make"
description: "Make outlines, literal includes, and source/target prerequisites."
editUrl: false
sidebar:
  order: 46
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Make outlines, literal includes, and source/target prerequisites.

Conventional Makefiles use their containing directory as the invocation
directory; imported fragments inherit it. Standalone fragments use the
repository root. Literal file-local variable assignments are propagated until
an include invalidates their bindings. Recipes, computed variables, implicit
pattern rules, and VPATH searches are not executed or inferred.

## Structs

### <span id="struct.Make"></span><code style="font-size: 0.85em">struct Make</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Make structural outlines and static local dependencies.
