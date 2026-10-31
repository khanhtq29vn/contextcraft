---
title: "contextcraft-ai-core::languages::elixir"
description: "Elixir outlines, literal Mix dependencies, and local module references."
editUrl: false
sidebar:
  order: 24
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Elixir outlines, literal Mix dependencies, and local module references.

Resolves literal path and umbrella dependencies, lexical aliases, module
directives, and remote module calls. Mix code and macros are not executed;
computed project settings and dynamically generated modules are not resolved.

## Structs

### <span id="struct.Elixir"></span><code style="font-size: 0.85em">struct Elixir</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Elixir grammar for `.ex` sources and `.exs` scripts.
