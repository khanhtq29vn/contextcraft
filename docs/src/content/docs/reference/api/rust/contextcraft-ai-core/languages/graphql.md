---
title: "contextcraft-ai-core::languages::graphql"
description: "GraphQL schema/operation outlines and explicitly imported local fragments."
editUrl: false
sidebar:
  order: 31
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

GraphQL schema/operation outlines and explicitly imported local fragments.

GraphQL-tools-style `# import` comments establish cross-file visibility.
Literal JSON/YAML GraphQL project document globs also establish visibility.
Executable configuration and fragments in unrelated projects are not inferred.

## Structs

### <span id="struct.Graphql"></span><code style="font-size: 0.85em">struct Graphql</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Graphql structural outlines and static local dependencies.
