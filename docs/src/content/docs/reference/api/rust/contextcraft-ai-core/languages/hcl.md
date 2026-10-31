---
title: "contextcraft-ai-core::languages::hcl"
description: "HCL outlines and Terraform directory-module dependencies."
editUrl: false
sidebar:
  order: 32
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

HCL outlines and Terraform directory-module dependencies.

Terraform `.tf` files share a module per directory. Literal local module
sources and unambiguous configuration traversals produce file dependencies.
Remote sources, templates, and iteration-scoped traversals are not evaluated.

## Structs

### <span id="struct.Hcl"></span><code style="font-size: 0.85em">struct Hcl</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Hcl structural outlines and static local dependencies.
