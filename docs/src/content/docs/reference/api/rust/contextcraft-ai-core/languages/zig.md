---
title: "contextcraft-ai-core::languages::zig"
description: "Zig declaration outlines and literal file dependencies."
editUrl: false
sidebar:
  order: 72
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Zig declaration outlines and literal file dependencies.

Resolves relative `.zig` imports and embedded files within the repository,
including binary embeds. Named modules, escaped or computed paths, Zig package
manifests, and build-script module wiring are not resolved. Build scripts and
compile-time code are never executed; nested `build.zig` files define package
boundaries, not inferred workspace membership.

## Structs

### <span id="struct.Zig"></span><code style="font-size: 0.85em">struct Zig</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Zig grammar for `.zig` sources, including `build.zig`.
