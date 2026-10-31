---
title: "contextcraft-ai-core::tiers"
description: "Render reusable fidelity tiers and lazily cache their framed token costs."
editUrl: false
sidebar:
  order: 76
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Render reusable fidelity tiers and lazily cache their framed token costs.

## Structs

### <span id="struct.RenderedTier"></span><code style="font-size: 0.85em">struct RenderedTier</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Shared tier content with a lazily counted framed token cost.

Cloning shares the content but copies the current token-cost cache. Concurrent
readers may compute the same cost before one result is cached. Cached costs
apply only to the path, fidelity level, format, and encoding used to count them.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `content` | `Arc<str>` | Rendered source outline, full source, or path for the path-only tier.<br>Do not replace content after its framed token cost has been cached. |

#### Methods

##### <span id="RenderedTier.framed_tokens"></span><code>framed_​tokens</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn framed_tokens(&self) -> usize
```

Returns the exact framed cost if cached, otherwise a byte-based estimate.

<details>
<summary>Source</summary>

```rust
    pub fn framed_tokens(&self) -> usize {
        self.framed_tokens
            .get()
            .copied()
            .unwrap_or(self.estimated_framed_tokens)
    }
```

</details>

### <span id="struct.FileTiers"></span><code style="font-size: 0.85em">struct FileTiers</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Available fidelity tiers for one indexed file.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `levels` | `[Option<RenderedTier>; 4]` | Tiers indexed by `FidelityLevel as usize`, from path-only to full source. |

### <span id="struct.Tiers"></span><code style="font-size: 0.85em">struct Tiers</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`, `PartialEq`, `Eq`

Per-file tiers tied to one output format and tokenizer encoding.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `output_format` | `OutputFormat` | Serialization format used to frame and cost these tiers. |
| `tokenizer_encoding` | `TokenizerEncoding` | Vocabulary used for cached exact token costs. |
| `token_counts_estimated` | `bool` | Whether the tier costs include fallback token estimates. |
| `files` | `ArenaMap<FileId, FileTiers>` | Available tiers keyed by IDs from the associated index. |

### <span id="struct.TierRenderer"></span><code style="font-size: 0.85em">struct TierRenderer</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Builds outlines from captured byte ranges without reparsing source.

#### Methods

##### <span id="TierRenderer.render"></span><code>render</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn render(
    index: &Index,
    repository: &Repository,
    config: &Config,
) -> Result<Tiers, Error>
```

Renders tiers, using a placeholder when a supported language has no outline. Unsupported files retain the richer-source fallback.

Files without readable source receive only a path-only tier.

**Errors:**

This implementation does not return errors.

**Panics:**

Panics if manually edited sources are not UTF-8 or a parsed file refers
to a language missing from the index.

<details>
<summary>Source</summary>

```rust
    pub fn render(index: &Index, repository: &Repository, config: &Config) -> Result<Tiers, Error> {
        let render_file = |(file_id, file): (FileId, &File)| {
            let path = file
                .path
                .to_string_lossy()
                .replace(std::path::MAIN_SEPARATOR, "/");
            let tree = RenderedTier {
                content: Arc::from(path.as_str()),
                // Path listings are budgeted separately from file blocks.
                estimated_framed_tokens: 0,
                framed_tokens: OnceLock::from(0),
            };
            let mut levels = [Some(tree), None, None, None];

            if let Some(source) = repository.sources.get(file_id) {
                let content =
                    std::str::from_utf8(&source.bytes).expect("repository source is UTF-8");
                let full = RenderedTier::new(
                    Arc::from(content),
                    &path,
                    FidelityLevel::Full,
                    config.output_format,
                );
                levels[FidelityLevel::Full as usize] = Some(full);

                for (level, richer) in [
                    (FidelityLevel::Skel, FidelityLevel::Full),
                    (FidelityLevel::Sigs, FidelityLevel::Skel),
                ] {
                    let rendered = if let (Some(language), Some(analysis)) =
                        (file.language, source.analysis.as_ref())
                    {
                        let language = &index.languages[language];

                        let outline = if level == FidelityLevel::Skel {
                            language.render_skel(content, analysis)
                        } else {
                            language.render_sigs(content, analysis)
                        };

                        if outline.trim().is_empty() {
                            "Outline unavailable; use FULL for source.".into()
                        } else {
                            outline
                        }
                    } else {
                        String::new()
                    };
                    let richer = levels[richer as usize]
                        .as_ref()
                        .expect("richer tier was rendered first");
                    let tier = compressed(rendered, richer, &path, level, config.output_format);
                    levels[level as usize] = Some(tier);
                }
            }

            (file_id, FileTiers { levels })
        };

        let files = if config.enable_parallel {
            let files: Vec<_> = index.files.iter().collect();
            let rendered: Vec<_> = files.into_par_iter().map(render_file).collect();
            rendered.into_iter().collect()
        } else {
            index.files.iter().map(render_file).collect()
        };

        Ok(Tiers {
            output_format: config.output_format,
            tokenizer_encoding: config.tokenizer_encoding,
            token_counts_estimated: false,
            files,
        })
    }
```

</details>

## Enums

### <span id="enum.FidelityLevel"></span><code style="font-size: 0.85em">enum FidelityLevel</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Increasing levels of source detail available to the budget allocator.

#### Variants

- **`Tree`** - Path-only listing with no source block.
- **`Sigs`** - Declaration headers and imports, with richer content as a fallback.
- **`Skel`** - Documented declaration outline, with full content as a fallback.
- **`Full`** - Complete readable source after optional secret redaction.

#### Methods

##### <span id="FidelityLevel.semantic_utility"></span><code>semantic_​utility</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn semantic_utility(self) -> f64
```

Returns the allocator's relative utility weight, from `0.0` to `1.0`.

<details>
<summary>Source</summary>

```rust
    pub fn semantic_utility(self) -> f64 {
        match self {
            Self::Tree => 0.0,
            Self::Sigs => 0.45,
            Self::Skel => 0.82,
            Self::Full => 1.0,
        }
    }
```

</details>

##### <span id="FidelityLevel.as_str"></span><code>as_​str</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn as_str(self) -> &'static str
```

Returns the uppercase label used in serialized file blocks.

<details>
<summary>Source</summary>

```rust
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Tree => "TREE",
            Self::Sigs => "SIGS",
            Self::Skel => "SKEL",
            Self::Full => "FULL",
        }
    }
```

</details>
