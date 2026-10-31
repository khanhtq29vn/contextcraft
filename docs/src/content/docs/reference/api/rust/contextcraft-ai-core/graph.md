---
title: "contextcraft-ai-core::graph"
description: "Directed local file dependencies and relevance scoring."
editUrl: false
sidebar:
  order: 9
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Directed local file dependencies and relevance scoring.

## Re-exports

- [`GraphScorer`](../../../rust/contextcraft-ai-core/graph/scorer/#struct.GraphScorer)

## Structs

### <span id="struct.Graph"></span><code style="font-size: 0.85em">struct Graph</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Edges point from an importing or declaring file to its local dependency. Includes possible dependencies across build configurations and optional environments.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `dependencies` | `DiGraphMap<FileId, ()>` | Directed file dependency edges using IDs from the associated index. |

#### Methods

##### <span id="Graph.new"></span><code>new</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn new(index: &Index, repository: &Repository) -> Self
```

Builds a graph from the language dependency analyses.

Includes every indexed file as a node and excludes self-dependency edges.

<details>
<summary>Source</summary>

```rust
    pub fn new(index: &Index, repository: &Repository) -> Self {
        let mut dependencies = DiGraphMap::new();

        for (file, _) in index.files.iter() {
            dependencies.add_node(file);
        }

        for language in index.languages.values() {
            for (from, to) in language.resolve_dependencies(index, repository) {
                if from != to {
                    dependencies.add_edge(from, to, ());
                }
            }
        }

        Self { dependencies }
    }
```

</details>

##### <span id="Graph.edge_count"></span><code>edge_​count</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn edge_count(&self) -> usize
```

Returns the number of distinct directed dependency edges.

<details>
<summary>Source</summary>

```rust
    pub fn edge_count(&self) -> usize {
        self.dependencies.edge_count()
    }
```

</details>

##### <span id="Graph.neighbors"></span><code>neighbors</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn neighbors(&self, file: FileId) -> impl Iterator<Item = FileId> + '_
```

Iterates over the local dependencies of a file.

Iteration order is unspecified. Unknown IDs produce an empty iterator.

<details>
<summary>Source</summary>

```rust
    pub fn neighbors(&self, file: FileId) -> impl Iterator<Item = FileId> + '_ {
        self.dependencies.neighbors(file)
    }
```

</details>
