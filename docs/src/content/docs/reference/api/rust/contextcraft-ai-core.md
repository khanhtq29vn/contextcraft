---
title: "contextcraft-ai-core"
description: "AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs."
editUrl: false
sidebar:
  order: 6
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.

[`ContextCraft::run`](../../rust/contextcraft-ai-core/#ContextCraft.run) indexes local packages, reads and redacts source files,
resolves dependencies, ranks files, and selects a fidelity level for each file.
The individual pipeline stages are also available through their modules.

Pipeline data uses public fields rather than accessors. File and package IDs
belong to the index that created them. Keep IDs and language registrations
consistent when editing data, and rebuild downstream stages after changes.

```rust
use contextcraft_core::{Config, ContextCraft};

let analysis = ContextCraft::new(Config::default()).run(".")?;
println!("{}", analysis.artifact.content);
```

## Structs

### <span id="struct.RepositoryAnalysis"></span><code style="font-size: 0.85em">struct RepositoryAnalysis</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Intermediate pipeline data and the final budgeted artifact.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `index` | `Index` | Indexed files, package ownership, and language implementations. |
| `repository` | `Repository` | Readable source files and extracted language state. |
| `graph` | `Graph` | Directed local file dependencies used for ranking. |
| `scores` | `ArenaMap<FileId, f64>` | Normalized relevance scores keyed by this analysis's file IDs. |
| `tiers` | `Tiers` | Rendered fidelity tiers with lazily cached token costs. |
| `artifact` | `Artifact` | Final serialized context and its token count. |

### <span id="struct.ContextCraft"></span><code style="font-size: 0.85em">struct ContextCraft</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Repository compression pipeline configured with [`Config`](../../rust/contextcraft-ai-core/#struct.Config).

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `config` | `Config` | Settings used by the next call to `Self::run`. |

#### Methods

##### <span id="ContextCraft.new"></span><code>new</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn new(config: Config) -> Self
```

Creates a pipeline with the supplied configuration.

<details>
<summary>Source</summary>

```rust
    pub fn new(config: Config) -> Self {
        Self { config }
    }
```

</details>

##### <span id="ContextCraft.run"></span><code>run</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn run(
    &self,
    root: impl AsRef<Path>,
) -> Result<RepositoryAnalysis, Error>
```

Analyzes a local repository and renders its compressed context.

Each call reads and analyzes the repository again.

**Errors:**

Returns an error if the root is not a directory, repository access or
manifest parsing fails, source analysis fails, or output framing cannot
fit within the token budget.

<details>
<summary>Source</summary>

```rust
    pub fn run(&self, root: impl AsRef<Path>) -> Result<RepositoryAnalysis, Error> {
        let index = Indexer::new().index(root, &self.config)?;
        let repository = RepositoryReader::new().read(&index, &self.config)?;
        let graph = Graph::new(&index, &repository);
        let scores = GraphScorer::score(&index, &repository, &graph, &self.config);
        let tiers = TierRenderer::render(&index, &repository, &self.config)?;
        let selection = BudgetAllocator::allocate(&index, &tiers, &scores, &self.config)?;
        let artifact =
            ArtifactFormatter::format(&index, &tiers, &scores, &selection, &self.config)?;

        Ok(RepositoryAnalysis {
            index,
            repository,
            graph,
            scores,
            tiers,
            artifact,
        })
    }
```

</details>

### <span id="struct.Config"></span><code style="font-size: 0.85em">struct Config</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`

Repository scanning, ranking, and output settings.

Construct custom settings with struct update syntax to retain other defaults.

```rust
use std::num::NonZeroUsize;
use contextcraft_core::{Config, ContextCraft, OutputFormat};

let mut pipeline = ContextCraft::new(Config {
    budget_tokens: NonZeroUsize::new(8_000).unwrap(),
    output_format: OutputFormat::Json,
    ..Config::default()
});
pipeline.config.focus_query = Some("authentication".into());
```

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `enable_parallel` | `bool` | Runs source analysis and tier rendering with Rayon. Defaults to `true`. |
| `budget_tokens` | `NonZeroUsize` | Maximum token count for the complete serialized artifact.<br>Defaults to 16,000. Rendering fails if even empty output framing cannot fit. |
| `focus_query` | `Option<String>` | Task description used for lexical relevance and personalized ranking.<br>Defaults to `None`, leaving ranking unbiased by a text query. |
| `focus_files` | `Vec<String>` | Paths, directories, filenames, or globs to favor during ranking.<br>Directory matches respect path boundaries. Wildcards may span separators. Defaults to an empty list. Matching files are favored, not guaranteed inclusion. |
| `output_format` | `OutputFormat` | Artifact serialization format. Defaults to [`OutputFormat::Markdown`](../../rust/contextcraft-ai-core/#enum.OutputFormat). |
| `exclude_patterns` | `Vec<String>` | Exclusions in `ignore::overrides` glob syntax, without the `!` prefix.<br>Paths are relative to the repository root. Defaults to an empty list. |
| `respect_gitignore` | `bool` | Honors repository, global, and explicit Git exclusion rules.<br>Defaults to `true`. Language-specific exclusions still apply when disabled. |
| `redact_secrets` | `bool` | Replaces recognized secrets before source analysis and rendering.<br>Defaults to `true`. Replacement preserves byte offsets and line breaks. Detection is limited to configured secret types, not every possible secret. |
| `max_file_size_bytes` | `NonZeroUsize` | Maximum source size to read. Larger files remain available as paths only.<br>Also bounds manifest reads. Defaults to 1,048,576 bytes (1 MiB). |
| `tokenizer_encoding` | `TokenizerEncoding` | Vocabulary used for token costs. Defaults to [`TokenizerEncoding::Cl100kBase`](../../rust/contextcraft-ai-core/#enum.TokenizerEncoding). |
| `allow_token_estimates` | `bool` | Permits estimated counts supplied to individual pipeline stages.<br>Defaults to `true`. The current tokenizer always counts exactly and does not use a fallback. |

## Enums

### <span id="enum.OutputFormat"></span><code style="font-size: 0.85em">enum OutputFormat</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Serialization format for the generated artifact.

#### Variants

- **`Markdown`** - Markdown headings and fenced source blocks. The default format.
- **`Xml`** - XML elements with escaped paths and source content.
- **`Json`** - JSON containing a path listing and selected file blocks.

#### Methods

##### <span id="OutputFormat.as_str"></span><code>as_​str</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn as_str(self) -> &'static str
```

Returns the identifier used in configuration and serialized output.

<details>
<summary>Source</summary>

```rust
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Markdown => "markdown",
            Self::Xml => "xml",
            Self::Json => "json",
        }
    }
```

</details>

### <span id="enum.TokenizerEncoding"></span><code style="font-size: 0.85em">enum TokenizerEncoding</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Tokenizer vocabulary used to measure the output budget.

#### Variants

- **`Gpt2`** - Original GPT-2 vocabulary, named `gpt2`.
- **`R50kBase`** - GPT-3 vocabulary, named `r50k_base`.
- **`P50kBase`** - Codex vocabulary, named `p50k_base`.
- **`P50kEdit`** - Edit-model vocabulary, named `p50k_edit`.
- **`Cl100kBase`** - Vocabulary named `cl100k_base`. The default encoding.
- **`O200kBase`** - Vocabulary named `o200k_base`.
- **`O200kHarmony`** - Harmony vocabulary, named `o200k_harmony`.

#### Methods

##### <span id="TokenizerEncoding.as_str"></span><code>as_​str</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn as_str(self) -> &'static str
```

Returns the identifier used in configuration and serialized output.

<details>
<summary>Source</summary>

```rust
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Gpt2 => "gpt2",
            Self::R50kBase => "r50k_base",
            Self::P50kBase => "p50k_base",
            Self::P50kEdit => "p50k_edit",
            Self::Cl100kBase => "cl100k_base",
            Self::O200kBase => "o200k_base",
            Self::O200kHarmony => "o200k_harmony",
        }
    }
```

</details>
