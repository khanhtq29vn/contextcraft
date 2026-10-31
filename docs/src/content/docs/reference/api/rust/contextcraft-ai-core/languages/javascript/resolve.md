---
title: "contextcraft-ai-core::languages::javascript::resolve"
description: "Resolve captured references to indexed local files."
editUrl: false
sidebar:
  order: 37
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Resolve captured references to indexed local files.

## Functions

### <span id="fn.resolve"></span><code style="font-size: 0.85em">fn resolve</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn resolve(
    index: &Index,
    repository: &Repository,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)>
```

Resolves relative script imports to readable scripts, components, JSON, and stylesheets.

Resolves declared local workspace packages, package exports, and static JSONC
path aliases. Unknown runtime/bundler conditions remain unresolved.

<details>
<summary>Source</summary>

```rust
pub fn resolve(
    index: &Index,
    repository: &Repository,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)> {
    resolve_components(index, repository, imports, &HashSet::new())
}
```

</details>
