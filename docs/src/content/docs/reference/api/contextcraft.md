---
title: "contextcraft"
description: "AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs."
editUrl: false
sidebar:
  order: 1
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-blue-low); color: var(--sl-color-blue-high);">Python</span>

AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.

Create a Config, pass it to ContextCraft, and call run() on a local directory.
The returned RepositoryAnalysis contains the final artifact and pipeline data.

## Variables

| Name | Type | Description |
|------|------|-------------|
| `__all__` | `list` |  |

## Classes

### <span id="class.Config"></span><code style="font-size: 0.85em">class Config</code>

> **Rust Implementation**: [`contextcraft-ai::Config`](../rust/contextcraft-ai/#struct.Config)

Mutable scanning, ranking, and output settings.

Numeric limits must be positive. Assign new lists to update collection fields.
Reading a collection field returns a copy rather than a live mutable view.

#### Methods

##### <span id="Config.new"></span><code>new</code>

```python
def new(kwargs: Optional[Bound<'_, PyDict>]) -> Self
```

> **Rust Implementation**: [`contextcraft-ai::Config::new`](../rust/contextcraft-ai/#Config.new)

Creates settings with the same defaults as the Rust core.

Raises ValueError if a numeric limit is zero.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `kwargs` | `Optional[Bound<'_, PyDict>]` |  |

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

### <span id="class.ContextCraft"></span><code style="font-size: 0.85em">class ContextCraft</code>

> **Rust Implementation**: [`contextcraft-ai::ContextCraft`](../rust/contextcraft-ai/#struct.ContextCraft)

Configurable repository compression pipeline.

#### Methods

##### <span id="ContextCraft.new"></span><code>new</code>

```python
def new(config: Optional[Py<Config>]) -> Self
```

> **Rust Implementation**: [`contextcraft-ai::ContextCraft::new`](../rust/contextcraft-ai/#ContextCraft.new)

Creates a pipeline, retaining the supplied Config or creating default settings.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `config` | `Optional[Py<Config>]` |  |

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

```python
def run(root: PathBuf) -> RepositoryAnalysis
```

> **Rust Implementation**: [`contextcraft-ai::ContextCraft::run`](../rust/contextcraft-ai/#ContextCraft.run)

Analyzes a local directory and returns a snapshot with its budgeted artifact.

Accepts a string or os.PathLike path. Each run rereads the repository and
releases the GIL during Rust analysis. Settings are copied before analysis.

Raises OSError for filesystem failures, ValueError for invalid settings,
manifests, or an insufficient budget, and RuntimeError for analysis failures.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` |  |

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

### <span id="class.File"></span><code style="font-size: 0.85em">class File</code>

> **Rust Implementation**: [`contextcraft-ai::File`](../rust/contextcraft-ai/#struct.File)

Repository-relative file metadata. IDs are local to the containing index.

### <span id="class.PackageDependency"></span><code style="font-size: 0.85em">class PackageDependency</code>

> **Rust Implementation**: [`contextcraft-ai::PackageDependency`](../rust/contextcraft-ai/#struct.PackageDependency)

Named dependency on another indexed local package.

### <span id="class.Package"></span><code style="font-size: 0.85em">class Package</code>

> **Rust Implementation**: [`contextcraft-ai::Package`](../rust/contextcraft-ai/#struct.Package)

Local package metadata shared by language implementations.

### <span id="class.Workspace"></span><code style="font-size: 0.85em">class Workspace</code>

> **Rust Implementation**: [`contextcraft-ai::Workspace`](../rust/contextcraft-ai/#struct.Workspace)

Language-specific local workspace membership.

### <span id="class.Index"></span><code style="font-size: 0.85em">class Index</code>

> **Rust Implementation**: [`contextcraft-ai::Index`](../rust/contextcraft-ai/#struct.Index)

Discovered repository files, packages, workspaces, and language IDs.

### <span id="class.Analysis"></span><code style="font-size: 0.85em">class Analysis</code>

> **Rust Implementation**: [`contextcraft-ai::Analysis`](../rust/contextcraft-ai/#struct.Analysis)

Outline capture ranges as half-open UTF-8 byte offsets into Source.bytes.

### <span id="class.Source"></span><code style="font-size: 0.85em">class Source</code>

> **Rust Implementation**: [`contextcraft-ai::Source`](../rust/contextcraft-ai/#struct.Source)

Readable UTF-8 source after optional secret redaction.

### <span id="class.Repository"></span><code style="font-size: 0.85em">class Repository</code>

> **Rust Implementation**: [`contextcraft-ai::Repository`](../rust/contextcraft-ai/#struct.Repository)

Readable sources from a repository snapshot.

### <span id="class.Graph"></span><code style="font-size: 0.85em">class Graph</code>

> **Rust Implementation**: [`contextcraft-ai::Graph`](../rust/contextcraft-ai/#struct.Graph)

Directed local file dependencies with importer-to-dependency edges.

### <span id="class.RenderedTier"></span><code style="font-size: 0.85em">class RenderedTier</code>

> **Rust Implementation**: [`contextcraft-ai::RenderedTier`](../rust/contextcraft-ai/#struct.RenderedTier)

Rendered source content and its cached or estimated framed token cost.

### <span id="class.FileTiers"></span><code style="font-size: 0.85em">class FileTiers</code>

> **Rust Implementation**: [`contextcraft-ai::FileTiers`](../rust/contextcraft-ai/#struct.FileTiers)

Available fidelity levels for one indexed file.

### <span id="class.Tiers"></span><code style="font-size: 0.85em">class Tiers</code>

> **Rust Implementation**: [`contextcraft-ai::Tiers`](../rust/contextcraft-ai/#struct.Tiers)

Rendered tiers tied to the run's output format and tokenizer vocabulary.

### <span id="class.Artifact"></span><code style="font-size: 0.85em">class Artifact</code>

> **Rust Implementation**: [`contextcraft-ai::Artifact`](../rust/contextcraft-ai/#struct.Artifact)

Serialized repository context and the final selected fidelity levels.

### <span id="class.RepositoryAnalysis"></span><code style="font-size: 0.85em">class RepositoryAnalysis</code>

> **Rust Implementation**: [`contextcraft-ai::RepositoryAnalysis`](../rust/contextcraft-ai/#struct.RepositoryAnalysis)

Analysis snapshot returned by ContextCraft.run.

Attributes are read-only. Collection attributes return copies containing
shared snapshot objects. Integer IDs only identify files or packages here.

### <span id="class.TokenCounter"></span><code style="font-size: 0.85em">class TokenCounter</code>

> **Rust Implementation**: [`contextcraft-ai::TokenCounter`](../rust/contextcraft-ai/#struct.TokenCounter)

Exact text token counter using the Rust tokenizer.

#### Methods

##### <span id="TokenCounter.new"></span><code>new</code>

```python
def new(encoding: TokenizerEncoding, allow_estimates: bool) -> Self
```

> **Rust Implementation**: [`contextcraft-ai::TokenCounter::new`](../rust/contextcraft-ai/#TokenCounter.new)

Creates a counter. The current implementation does not use estimates.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `encoding` | `TokenizerEncoding` |  |
| `allow_estimates` | `bool` |  |

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

```python
def count(content: str) -> int
```

> **Rust Implementation**: [`contextcraft-ai::TokenCounter::count`](../rust/contextcraft-ai/#TokenCounter.count)

Counts special-token markers as ordinary text, releasing the GIL while counting.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `content` | `str` |  |

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

```python
def count_full_sources(tiers: Tiers, enable_parallel: bool) -> Dict[str, Any]
```

> **Rust Implementation**: [`contextcraft-ai::TokenCounter::count_full_sources`](../rust/contextcraft-ai/#TokenCounter.count_full_sources)

Counts FULL-tier source text by file ID without copying content into Python.

Releases the GIL while counting. Files without a FULL tier are omitted.
With enable_parallel=True, counts files using the shared Rayon thread pool.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tiers` | `Tiers` |  |
| `enable_parallel` | `bool` |  |

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

```python
def used_estimates() -> bool
```

> **Rust Implementation**: [`contextcraft-ai::TokenCounter::used_estimates`](../rust/contextcraft-ai/#TokenCounter.used_estimates)

Returns False because the current tokenizer always counts exactly.

<details>
<summary>Source</summary>

```rust
    fn used_estimates(&self) -> bool {
        self.counter.used_estimates()
    }
```

</details>
