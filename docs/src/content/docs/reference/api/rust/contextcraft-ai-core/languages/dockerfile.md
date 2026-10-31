---
title: "contextcraft-ai-core::languages::dockerfile"
description: "Containerfile/Dockerfile outlines using `tree-sitter-containerfile`."
editUrl: false
sidebar:
  order: 23
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Containerfile/Dockerfile outlines using `tree-sitter-containerfile`.

Root-level build files use the repository root as their conventional build
context. COPY/ADD edges honor the applicable Docker ignore file. Nested build
files, external contexts/stages, ONBUILD payloads, and expanded paths remain
unresolved because their build context is not declared by the source file.

## Structs

### <span id="struct.Dockerfile"></span><code style="font-size: 0.85em">struct Dockerfile</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Containerfile grammar with explicitly bounded local build-context resolution.
