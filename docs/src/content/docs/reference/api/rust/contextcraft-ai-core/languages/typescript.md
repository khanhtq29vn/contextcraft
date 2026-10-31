---
title: "contextcraft-ai-core::languages::typescript"
description: "TypeScript and TSX parsing with JavaScript package ownership."
editUrl: false
sidebar:
  order: 69
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

TypeScript and TSX parsing with JavaScript package ownership.

## Structs

### <span id="struct.TypeScript"></span><code style="font-size: 0.85em">struct TypeScript</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

TypeScript grammar configuration. Defaults to TypeScript without JSX.

#### Methods

##### <span id="TypeScript.tsx"></span><code>tsx</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn tsx() -> Self
```

Creates a configuration using the TSX grammar to parse TypeScript with JSX.

<details>
<summary>Source</summary>

```rust
    pub fn tsx() -> Self {
        Self { tsx: true }
    }
```

</details>
