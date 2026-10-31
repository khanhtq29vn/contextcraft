---
title: "contextcraft-ai-core::languages::cmake"
description: "CMake command/function/target outlines and static local file dependencies."
editUrl: false
sidebar:
  order: 17
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

CMake command/function/target outlines and static local file dependencies.

Resolves literal `include`, `add_subdirectory`, and target source paths without
executing CMake. Includes keep the caller's source directory; subdirectories
establish a new one. Current-list/current-source directory variables are known;
unconditional literal set/list variables are propagated without evaluation.
Computed variables, module search paths, generated files, and deferred function
or macro calls are not inferred. Standalone scripts use the repository root.

## Structs

### <span id="struct.CMake"></span><code style="font-size: 0.85em">struct CMake</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

CMake structural outlines.
