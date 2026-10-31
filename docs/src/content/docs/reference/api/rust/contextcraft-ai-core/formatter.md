---
title: "contextcraft-ai-core::formatter"
description: "Render escaped Markdown, XML, or JSON and enforce the final token budget."
editUrl: false
sidebar:
  order: 8
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Render escaped Markdown, XML, or JSON and enforce the final token budget.

## Structs

### <span id="struct.Artifact"></span><code style="font-size: 0.85em">struct Artifact</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Serialized repository context and the fidelity levels included in it.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `content` | `String` | Complete serialized context, including path listings and framing. |
| `tokens` | `usize` | Token count for the complete serialized content. |
| `token_counts_estimated` | `bool` | Whether any input or final token count used an estimate. |
| `selected_tiers` | `ArenaMap<FileId, FidelityLevel>` | Final fidelity level for every indexed file, including path-only files. |

### <span id="struct.ArtifactFormatter"></span><code style="font-size: 0.85em">struct ArtifactFormatter</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Serializes selected tiers and downgrades them if the final output is too large.

#### Methods

##### <span id="ArtifactFormatter.render_file"></span><code>render_​file</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn render_file(
    path: &str,
    content: &str,
    level: FidelityLevel,
    format: OutputFormat,
) -> String
```

Renders one escaped file block. The path-only tier produces no block.

**Examples:**

JSON output escapes source text so the block can be parsed independently.

```rust
use contextcraft_core::OutputFormat;
use contextcraft_core::formatter::ArtifactFormatter;
use contextcraft_core::tiers::FidelityLevel;

let block = ArtifactFormatter::render_file(
    "src/main.rs",
    "fn main() { println!(\"hello\"); }\n",
    FidelityLevel::Full,
    OutputFormat::Json,
);
let file: serde_json::Value = serde_json::from_str(&block)?;
assert_eq!(file["path"], "src/main.rs");
assert_eq!(file["content"], "fn main() { println!(\"hello\"); }\n");
```

<details>
<summary>Source</summary>

```rust
    pub fn render_file(
        path: &str,
        content: &str,
        level: FidelityLevel,
        format: OutputFormat,
    ) -> String {
        if level == FidelityLevel::Tree {
            return String::new();
        }

        match format {
            OutputFormat::Json => format!(
                "{{\"path\":{},\"tier\":\"{}\",\"content\":{}}}",
                json_string(path),
                level.as_str(),
                json_string(content),
            ),
            OutputFormat::Xml => {
                let path = escape_xml(path, true);

                if content.is_empty() {
                    format!("<file path=\"{path}\" tier=\"{}\" />", level.as_str())
                } else {
                    format!(
                        "<file path=\"{path}\" tier=\"{}\">{}</file>",
                        level.as_str(),
                        escape_xml(content, false)
                    )
                }
            }
            OutputFormat::Markdown => {
                let mut longest = 0;
                let mut run = 0;

                for byte in content.bytes() {
                    if byte == b'`' {
                        run += 1;
                        longest = longest.max(run);
                    } else {
                        run = 0;
                    }
                }

                let fence = "`".repeat(3.max(longest + 1));
                format!(
                    "## {} [{}]\n\n{fence}\n{content}\n{fence}\n\n",
                    json_string(path),
                    level.as_str()
                )
            }
        }
    }
```

</details>

##### <span id="ArtifactFormatter.file_cost"></span><code>file_​cost</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn file_cost(
    path: &str,
    content: &str,
    level: FidelityLevel,
    counter: &TokenCounter,
    format: OutputFormat,
) -> Result<usize, Error>
```

Counts a framed file block, including a trailing comma for JSON.

The path-only tier costs zero here because paths are budgeted separately.
Joined blocks must be recounted because BPE merges can span their boundaries.

**Errors:**

Propagates token-counting failures.

<details>
<summary>Source</summary>

```rust
    pub fn file_cost(
        path: &str,
        content: &str,
        level: FidelityLevel,
        counter: &TokenCounter,
        format: OutputFormat,
    ) -> Result<usize, Error> {
        if level == FidelityLevel::Tree {
            return Ok(0);
        }

        let mut block = Self::render_file(path, content, level, format);

        if format == OutputFormat::Json {
            block.push(',');
        }

        counter.count(&block)
    }
```

</details>

##### <span id="ArtifactFormatter.render"></span><code>render</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn render(
    index: &Index,
    tiers: &Tiers,
    selection: &Selection,
    tree: &[FileId],
    config: &Config,
) -> Result<String, Error>
```

Serializes a selection and path listing without enforcing a token budget.

**Errors:**

Returns an error for inconsistent pipeline inputs, duplicate paths, or
paths that do not belong to the index.

<details>
<summary>Source</summary>

```rust
    pub fn render(
        index: &Index,
        tiers: &Tiers,
        selection: &Selection,
        tree: &[FileId],
        config: &Config,
    ) -> Result<String, Error> {
        tiers.validate(index, config)?;
        selection.validate(index, tiers)?;
        let mut seen = HashSet::new();

        if tree
            .iter()
            .any(|&file| tiers.files.get(file).is_none() || !seen.insert(file))
        {
            return Err(Error::InvalidPipeline(
                "path listings must contain unique indexed files",
            ));
        }

        let path = |file| {
            tiers.files[file].levels[FidelityLevel::Tree as usize]
                .as_ref()
                .unwrap()
                .content
                .as_ref()
        };
        let mut blocks = String::new();

        for (file, _) in index.files.iter() {
            let level = selection.tiers[file];

            if level == FidelityLevel::Tree {
                continue;
            }

            if config.output_format == OutputFormat::Json && !blocks.is_empty() {
                blocks.push(',');
            }

            let content = &tiers.files[file].levels[level as usize]
                .as_ref()
                .unwrap()
                .content;
            blocks.push_str(&Self::render_file(
                path(file),
                content,
                level,
                config.output_format,
            ));
        }

        let omitted = index.files.len() - tree.len();

        Ok(match config.output_format {
            OutputFormat::Json => {
                let paths: Vec<_> = tree.iter().map(|&file| path(file)).collect();
                let paths = serde_json::to_string(&paths).expect("paths serialize as JSON");
                format!("{{\"tree\":{paths},\"omitted_paths\":{omitted},\"files\":[{blocks}]}}")
            }
            OutputFormat::Xml => {
                let mut listing = format!("<tree omitted_paths=\"{omitted}\"");

                if tree.is_empty() {
                    listing.push_str(" />");
                } else {
                    listing.push('>');

                    for &file in tree {
                        listing.push_str("<file path=\"");
                        listing.push_str(&escape_xml(path(file), true));
                        listing.push_str("\" />");
                    }

                    listing.push_str("</tree>");
                }

                format!("<repository_context>{listing}<files>{blocks}</files></repository_context>")
            }
            OutputFormat::Markdown => {
                let mut output = String::from("# Repository context\n\n");

                for &file in tree {
                    output.push_str("- ");
                    output.push_str(&json_string(path(file)));
                    output.push('\n');
                }

                if omitted != 0 {
                    output.push_str(&format!("- {omitted} paths omitted\n"));
                }

                if !tree.is_empty() || omitted != 0 {
                    output.push('\n');
                }

                output.push_str(&blocks);
                output
            }
        })
    }
```

</details>

##### <span id="ArtifactFormatter.directory_tree"></span><code>directory_​tree</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn directory_tree(
    index: &Index,
    tiers: &Tiers,
    counter: &TokenCounter,
    config: &Config,
) -> Result<Vec<FileId>, Error>
```

Selects an index-ordered path listing using up to a tenth of the budget.

**Errors:**

Returns an error for inconsistent pipeline inputs, token-counting failures,
or a budget smaller than the empty output framing.

<details>
<summary>Source</summary>

```rust
    pub fn directory_tree(
        index: &Index,
        tiers: &Tiers,
        counter: &TokenCounter,
        config: &Config,
    ) -> Result<Vec<FileId>, Error> {
        let selection = Selection {
            tiers: index
                .files
                .iter()
                .map(|(file, _)| (file, FidelityLevel::Tree))
                .collect(),
            token_counts_estimated: tiers.token_counts_estimated,
        };
        let baseline = counter.count(&Self::render(index, tiers, &selection, &[], config)?)?;

        if baseline > config.budget_tokens.get() {
            return Err(Error::BudgetTooSmall {
                budget: config.budget_tokens.get(),
                minimum: baseline,
            });
        }

        let mut paths: Vec<_> = index.files.iter().map(|(file, _)| file).collect();
        let mut low = 0;
        let mut high = paths.len();

        while low < high {
            let middle = low + (high - low).div_ceil(2);
            let cost = counter.count(&Self::render(
                index,
                tiers,
                &selection,
                &paths[..middle],
                config,
            )?)?;

            if cost.saturating_sub(baseline) <= config.budget_tokens.get() / 10 {
                low = middle;
            } else {
                high = middle - 1;
            }
        }

        paths.truncate(low);
        paths.shrink_to_fit();
        Ok(paths)
    }
```

</details>

##### <span id="ArtifactFormatter.format"></span><code>format</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn format(
    index: &Index,
    tiers: &Tiers,
    scores: &ArenaMap<FileId, f64>,
    selection: &Selection,
    config: &Config,
) -> Result<Artifact, Error>
```

Renders a selection and downgrades tiers until the output fits the budget.

Recounts the complete output after each downgrade to account for token
boundaries between file blocks.

**Errors:**

Returns an error for inconsistent inputs, invalid scores, token-counting
failures, or a budget smaller than the output framing.

<details>
<summary>Source</summary>

```rust
    pub fn format(
        index: &Index,
        tiers: &Tiers,
        scores: &ArenaMap<FileId, f64>,
        selection: &Selection,
        config: &Config,
    ) -> Result<Artifact, Error> {
        tiers.validate(index, config)?;
        selection.validate(index, tiers)?;
        validate_scores(index, scores)?;

        if selection.token_counts_estimated && !config.allow_token_estimates {
            return Err(Error::InvalidPipeline(
                "strict counting requires an exact allocation",
            ));
        }

        let counter = TokenCounter::new(config.tokenizer_encoding, config.allow_token_estimates)?;
        let mut selected = selection.clone();
        let mut tree = Self::directory_tree(index, tiers, &counter, config)?;

        loop {
            let content = Self::render(index, tiers, &selected, &tree, config)?;
            let tokens = counter.count(&content)?;

            if tokens <= config.budget_tokens.get() {
                return Ok(Artifact {
                    content,
                    tokens,
                    token_counts_estimated: tiers.token_counts_estimated
                        || selected.token_counts_estimated
                        || counter.used_estimates(),
                    selected_tiers: selected.tiers,
                });
            }

            let mut best: Option<(f64, f64, FileId, FidelityLevel)> = None;

            for (file, &current) in selected.tiers.iter() {
                let path = &tiers.files[file].levels[FidelityLevel::Tree as usize]
                    .as_ref()
                    .unwrap()
                    .content;
                let current_tier = tiers.files[file].levels[current as usize].as_ref().unwrap();
                let current_cost =
                    current_tier.count(path, current, &counter, config.output_format)?;

                for lower in FidelityLevel::ALL
                    .into_iter()
                    .filter(|&level| level < current)
                {
                    let Some(tier) = tiers.files[file].levels[lower as usize].as_ref() else {
                        continue;
                    };
                    let cost = tier.count(path, lower, &counter, config.output_format)?;
                    let savings = current_cost.saturating_sub(cost);

                    if savings == 0 {
                        continue;
                    }

                    let loss =
                        scores[file] * (current.semantic_utility() - lower.semantic_utility());
                    let candidate = (loss / savings as f64, loss, file, lower);

                    if best.as_ref().is_none_or(|best| {
                        candidate
                            .0
                            .total_cmp(&best.0)
                            .then_with(|| candidate.1.total_cmp(&best.1))
                            .then_with(|| candidate.2.cmp(&best.2))
                            .then_with(|| candidate.3.cmp(&best.3))
                            .is_lt()
                    }) {
                        best = Some(candidate);
                    }
                }
            }

            if let Some((_, _, file, lower)) = best {
                selected.tiers[file] = lower;
            } else if !tree.is_empty() {
                tree.truncate(tree.len() / 2);
            } else {
                return Err(Error::BudgetTooSmall {
                    budget: config.budget_tokens.get(),
                    minimum: tokens,
                });
            }
        }
    }
```

</details>
