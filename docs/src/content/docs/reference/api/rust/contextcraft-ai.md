---
title: "contextcraft-ai"
description: "Python bindings for AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs."
editUrl: false
sidebar:
  order: 5
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Python bindings for AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.

## Structs

### <span id="struct.Config"></span><code style="font-size: 0.85em">class Config</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Config`](../../contextcraft/#class.Config)

Mutable scanning, ranking, and output settings.

Numeric limits must be positive. Assign new lists to update collection fields.
Reading a collection field returns a copy rather than a live mutable view.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `enable_parallel` | `bool` | Whether to analyze sources and render tiers in parallel. Defaults to True. |
| `budget_tokens` | `usize` | Maximum tokens in the complete artifact. Defaults to 16000. |
| `focus_query` | `Option<String>` | Optional task description used to bias relevance scores. |
| `focus_files` | `Vec<String>` | Paths, filenames, directories, or globs to favor, not force into output. |
| `output_format` | `OutputFormat` | Serialization format. Defaults to OutputFormat.MARKDOWN. |
| `exclude_patterns` | `Vec<String>` | Repository-relative exclusion globs without an exclusion prefix. |
| `respect_gitignore` | `bool` | Whether to honor Git ignore rules. Defaults to True. |
| `redact_secrets` | `bool` | Whether to redact recognized secrets before parsing. Defaults to True. |
| `max_file_size_bytes` | `usize` | Maximum source and manifest size in bytes. Defaults to 1048576. |
| `tokenizer_encoding` | `TokenizerEncoding` | Tokenizer vocabulary. Defaults to TokenizerEncoding.CL100K_BASE. |
| `allow_token_estimates` | `bool` | Whether pipeline estimates are permitted. The current tokenizer is exact. |

#### Methods

##### <span id="Config.new"></span><code>new</code>

```rust
fn new(kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self>
```

> **Python API**: [`contextcraft.Config.new`](../../contextcraft/#Config.new)

Creates settings with the same defaults as the Rust core.

Raises ValueError if a numeric limit is zero.

<details>
<summary>Source</summary>

```rust
    fn new(kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mut config = Self::default();

        if let Some(kwargs) = kwargs {
            for (key, value) in kwargs {
                let key: String = key.extract()?;

                match key.as_str() {
                    "enable_parallel" => config.enable_parallel = value.extract()?,
                    "budget_tokens" => config.budget_tokens = value.extract()?,
                    "focus_query" => config.focus_query = value.extract()?,
                    "focus_files" => {
                        config.focus_files =
                            value.extract::<Option<Vec<String>>>()?.unwrap_or_default();
                    }
                    "output_format" => config.output_format = value.extract()?,
                    "exclude_patterns" => {
                        config.exclude_patterns =
                            value.extract::<Option<Vec<String>>>()?.unwrap_or_default();
                    }
                    "respect_gitignore" => config.respect_gitignore = value.extract()?,
                    "redact_secrets" => config.redact_secrets = value.extract()?,
                    "max_file_size_bytes" => config.max_file_size_bytes = value.extract()?,
                    "tokenizer_encoding" => config.tokenizer_encoding = value.extract()?,
                    "allow_token_estimates" => config.allow_token_estimates = value.extract()?,
                    _ => {
                        return Err(PyTypeError::new_err(format!(
                            "unexpected Config argument: {key}"
                        )));
                    }
                }
            }
        }

        config.to_core()?;
        Ok(config)
    }
```

</details>

### <span id="struct.ContextCraft"></span><code style="font-size: 0.85em">class ContextCraft</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.ContextCraft`](../../contextcraft/#class.ContextCraft)

Configurable repository compression pipeline.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `config` | `Py<Config>` | Mutable settings read at the start of each run. |

#### Methods

##### <span id="ContextCraft.new"></span><code>new</code>

```rust
fn new(py: Python<'_>, config: Option<Py<Config>>) -> PyResult<Self>
```

> **Python API**: [`contextcraft.ContextCraft.new`](../../contextcraft/#ContextCraft.new)

Creates a pipeline, retaining the supplied Config or creating default settings.

<details>
<summary>Source</summary>

```rust
    fn new(py: Python<'_>, config: Option<Py<Config>>) -> PyResult<Self> {
        Ok(Self {
            config: match config {
                Some(config) => config,
                None => Py::new(py, Config::default())?,
            },
        })
    }
```

</details>

##### <span id="ContextCraft.run"></span><code>run</code>

```rust
fn run(
    &self,
    py: Python<'_>,
    root: PathBuf,
) -> PyResult<RepositoryAnalysis>
```

> **Python API**: [`contextcraft.ContextCraft.run`](../../contextcraft/#ContextCraft.run)

Analyzes a local directory and returns a snapshot with its budgeted artifact.

Accepts a string or os.PathLike path. Each run rereads the repository and
releases the GIL during Rust analysis. Settings are copied before analysis.

Raises OSError for filesystem failures, ValueError for invalid settings,
manifests, or an insufficient budget, and RuntimeError for analysis failures.

<details>
<summary>Source</summary>

```rust
    fn run(&self, py: Python<'_>, root: PathBuf) -> PyResult<RepositoryAnalysis> {
        let config = self.config.borrow(py).to_core()?;
        let analysis = py
            .detach(move || core::ContextCraft::new(config).run(root))
            .map_err(python_error)?;
        RepositoryAnalysis::from_core(py, analysis)
    }
```

</details>

### <span id="struct.File"></span><code style="font-size: 0.85em">class File</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.File`](../../contextcraft/#class.File)

Repository-relative file metadata. IDs are local to the containing index.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `path` | `PathBuf` | File path relative to the repository root. |
| `package_id` | `usize` | Owning package ID, including the fallback package when needed. |
| `language` | `Option<&'static str>` | Registered language ID, or None for an unsupported extension. |

### <span id="struct.PackageDependency"></span><code style="font-size: 0.85em">class PackageDependency</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.PackageDependency`](../../contextcraft/#class.PackageDependency)

Named dependency on another indexed local package.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `alias` | `String` | Language-specific dependency name or alias. |
| `package` | `usize` | Referenced package ID in the same index. |

### <span id="struct.Package"></span><code style="font-size: 0.85em">class Package</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Package`](../../contextcraft/#class.Package)

Local package metadata shared by language implementations.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Package directory relative to the repository root. |
| `name` | `Option<String>` | Declared package name, if available. |
| `language` | `Option<&'static str>` | Package language, or None for the fallback package. |
| `manifests` | `Vec<PathBuf>` | Repository-relative manifest paths. |
| `targets` | `Vec<usize>` | Indexed target entry file IDs. |
| `dependencies` | `Vec<Py<PackageDependency>>` | Explicit local package dependencies. |

### <span id="struct.Workspace"></span><code style="font-size: 0.85em">class Workspace</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Workspace`](../../contextcraft/#class.Workspace)

Language-specific local workspace membership.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Workspace directory relative to the repository root. |
| `language` | `&'static str` | Language defining the workspace. |
| `members` | `Vec<usize>` | Local package IDs belonging to this workspace. |

### <span id="struct.Index"></span><code style="font-size: 0.85em">class Index</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Index`](../../contextcraft/#class.Index)

Discovered repository files, packages, workspaces, and language IDs.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Canonical absolute repository directory. |
| `files` | `HashMap<usize, Py<File>>` | Indexed file metadata keyed by local integer file IDs. |
| `packages` | `HashMap<usize, Py<Package>>` | Package metadata keyed by local integer package IDs. |
| `workspaces` | `Vec<Py<Workspace>>` | Discovered workspace memberships. |
| `languages` | `Vec<&'static str>` | Sorted registered language IDs. Rust trait objects are not exported. |

### <span id="struct.Analysis"></span><code style="font-size: 0.85em">class Analysis</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Analysis`](../../contextcraft/#class.Analysis)

Outline capture ranges as half-open UTF-8 byte offsets into Source.bytes.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `docstrings` | `Vec<(usize, usize)>` | Documentation comment and docstring ranges. |
| `imports` | `Vec<(usize, usize)>` | Import statement ranges retained in outlines. |
| `sigs` | `Vec<(usize, usize)>` | Declaration header ranges used by signatures. |
| `skel` | `Vec<(usize, usize)>` | Additional documented outline ranges. |

### <span id="struct.Source"></span><code style="font-size: 0.85em">class Source</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Source`](../../contextcraft/#class.Source)

Readable UTF-8 source after optional secret redaction.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `bytes` | `Py<PyBytes>` | Immutable source bytes aligned with the captured ranges. |
| `analysis` | `Option<Py<Analysis>>` | Captured outline ranges, or None for an unparsed language. |

### <span id="struct.Repository"></span><code style="font-size: 0.85em">class Repository</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Repository`](../../contextcraft/#class.Repository)

Readable sources from a repository snapshot.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `sources` | `HashMap<usize, Py<Source>>` | Sources keyed by file ID. Skipped sources have no entry. |

### <span id="struct.Graph"></span><code style="font-size: 0.85em">class Graph</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Graph`](../../contextcraft/#class.Graph)

Directed local file dependencies with importer-to-dependency edges.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `dependencies` | `Vec<(usize, usize)>` | Sorted pairs of importing file ID and dependency file ID. |

### <span id="struct.RenderedTier"></span><code style="font-size: 0.85em">class RenderedTier</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.RenderedTier`](../../contextcraft/#class.RenderedTier)

Rendered source content and its cached or estimated framed token cost.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `content` | `String` | Source outline, full source, or path for the TREE tier. |
| `framed_tokens` | `usize` | Framed token cost. Unselected tiers may retain byte-based estimates. |

### <span id="struct.FileTiers"></span><code style="font-size: 0.85em">class FileTiers</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.FileTiers`](../../contextcraft/#class.FileTiers)

Available fidelity levels for one indexed file.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `levels` | `HashMap<FidelityLevel, Py<RenderedTier>>` | Available rendered tiers keyed by fidelity level. |

### <span id="struct.Tiers"></span><code style="font-size: 0.85em">class Tiers</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Tiers`](../../contextcraft/#class.Tiers)

Rendered tiers tied to the run's output format and tokenizer vocabulary.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `output_format` | `OutputFormat` | Serialization format used for framed costs. |
| `tokenizer_encoding` | `TokenizerEncoding` | Tokenizer vocabulary used for exact costs. |
| `token_counts_estimated` | `bool` | Whether the core reports fallback token estimates. |
| `files` | `HashMap<usize, Py<FileTiers>>` | Available tier data keyed by file ID. |

### <span id="struct.Artifact"></span><code style="font-size: 0.85em">class Artifact</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.Artifact`](../../contextcraft/#class.Artifact)

Serialized repository context and the final selected fidelity levels.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `content` | `String` | Complete context including path listings and output framing. |
| `tokens` | `usize` | Token count of the complete serialized context. |
| `token_counts_estimated` | `bool` | Whether any allocation or final token count used a fallback estimate. |
| `selected_tiers` | `HashMap<usize, FidelityLevel>` | Final fidelity level for every indexed file. |

### <span id="struct.RepositoryAnalysis"></span><code style="font-size: 0.85em">class RepositoryAnalysis</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.RepositoryAnalysis`](../../contextcraft/#class.RepositoryAnalysis)

Analysis snapshot returned by ContextCraft.run.

Attributes are read-only. Collection attributes return copies containing
shared snapshot objects. Integer IDs only identify files or packages here.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `index` | `Py<Index>` | Discovered repository structure and local package metadata. |
| `repository` | `Py<Repository>` | Loaded and optionally redacted sources. |
| `graph` | `Py<Graph>` | Directed file dependencies used for ranking. |
| `scores` | `HashMap<usize, f64>` | Normalized relevance scores keyed by file ID. |
| `tiers` | `Py<Tiers>` | Rendered source tiers and their cached or estimated costs. |
| `artifact` | `Py<Artifact>` | Final token-budgeted output. |

### <span id="struct.TokenCounter"></span><code style="font-size: 0.85em">class TokenCounter</code>

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-purple-low); color: var(--sl-color-purple-high);">Binding</span>

> **Python API**: [`contextcraft.TokenCounter`](../../contextcraft/#class.TokenCounter)

Exact text token counter using the Rust tokenizer.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `counter` | `core::tokens::TokenCounter` |  |

#### Methods

##### <span id="TokenCounter.new"></span><code>new</code>

```rust
fn new(
    encoding: TokenizerEncoding,
    allow_estimates: bool,
) -> PyResult<Self>
```

> **Python API**: [`contextcraft.TokenCounter.new`](../../contextcraft/#TokenCounter.new)

Creates a counter. The current implementation does not use estimates.

<details>
<summary>Source</summary>

```rust
    fn new(encoding: TokenizerEncoding, allow_estimates: bool) -> PyResult<Self> {
        Ok(Self {
            counter: core::tokens::TokenCounter::new(encoding.into(), allow_estimates)
                .map_err(python_error)?,
        })
    }
```

</details>

##### <span id="TokenCounter.count"></span><code>count</code>

```rust
fn count(&self, py: Python<'_>, content: String) -> PyResult<usize>
```

> **Python API**: [`contextcraft.TokenCounter.count`](../../contextcraft/#TokenCounter.count)

Counts special-token markers as ordinary text, releasing the GIL while counting.

<details>
<summary>Source</summary>

```rust
    fn count(&self, py: Python<'_>, content: String) -> PyResult<usize> {
        py.detach(|| self.counter.count(&content))
            .map_err(python_error)
    }
```

</details>

##### <span id="TokenCounter.count_full_sources"></span><code>count_​full_​sources</code>

```rust
fn count_full_sources(
    &self,
    py: Python<'_>,
    tiers: &Tiers,
    enable_parallel: bool,
) -> PyResult<HashMap<usize, usize>>
```

> **Python API**: [`contextcraft.TokenCounter.count_full_sources`](../../contextcraft/#TokenCounter.count_full_sources)

Counts FULL-tier source text by file ID without copying content into Python.

Releases the GIL while counting. Files without a FULL tier are omitted.
With enable_parallel=True, counts files using the shared Rayon thread pool.

<details>
<summary>Source</summary>

```rust
    fn count_full_sources(
        &self,
        py: Python<'_>,
        tiers: &Tiers,
        enable_parallel: bool,
    ) -> PyResult<HashMap<usize, usize>> {
        let count = |(&file, tiers): (&usize, &Py<FileTiers>)| {
            tiers.get().levels.get(&FidelityLevel::Full).map(|tier| {
                self.counter
                    .count(&tier.get().content)
                    .map(|tokens| (file, tokens))
            })
        };

        py.detach(|| -> Result<HashMap<usize, usize>, core::error::Error> {
            if enable_parallel {
                tiers.files.par_iter().filter_map(count).collect()
            } else {
                tiers.files.iter().filter_map(count).collect()
            }
        })
        .map_err(python_error)
    }
```

</details>

##### <span id="TokenCounter.used_estimates"></span><code>used_​estimates</code>

```rust
fn used_estimates(&self) -> bool
```

> **Python API**: [`contextcraft.TokenCounter.used_estimates`](../../contextcraft/#TokenCounter.used_estimates)

Returns False because the current tokenizer always counts exactly.

<details>
<summary>Source</summary>

```rust
    fn used_estimates(&self) -> bool {
        self.counter.used_estimates()
    }
```

</details>
