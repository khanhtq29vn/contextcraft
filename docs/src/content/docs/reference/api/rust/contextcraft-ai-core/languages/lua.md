---
title: "contextcraft-ai-core::languages::lua"
description: "Lua outlines, LuaRocks metadata, and static local module dependencies."
editUrl: false
sidebar:
  order: 44
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Lua outlines, LuaRocks metadata, and static local module dependencies.

Resolves literal `require`, `dofile`, and `loadfile` calls. Module lookup uses
declared rockspec mappings and conventional root, `src`, and `lua` directories.
Runtime changes to `package.path`, custom loaders, and executable rockspec logic
are not evaluated. Local rock names must be unambiguous.

## Structs

### <span id="struct.Lua"></span><code style="font-size: 0.85em">struct Lua</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Lua grammar and local project analysis.
