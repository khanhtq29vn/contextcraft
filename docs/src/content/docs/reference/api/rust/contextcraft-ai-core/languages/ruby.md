---
title: "contextcraft-ai-core::languages::ruby"
description: "Ruby `.rb` outlines, local Bundler gems, and literal load dependencies."
editUrl: false
sidebar:
  order: 54
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Ruby `.rb` outlines, local Bundler gems, and literal load dependencies.

Reads literal gemspec names/load paths and Gemfile path dependencies without
executing Ruby. Resolves `require_relative`, local-gem `require`, and literal
repository-relative `load`. Dynamic load paths and metaprogramming remain unresolved.

## Structs

### <span id="struct.Ruby"></span><code style="font-size: 0.85em">struct Ruby</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Ruby grammar and local project analysis.
