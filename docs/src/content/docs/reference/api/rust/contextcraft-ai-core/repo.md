---
title: "contextcraft-ai-core::repo"
description: "Read, redact, and analyze repository source files."
editUrl: false
sidebar:
  order: 75
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Read, redact, and analyze repository source files.

## Structs

### <span id="struct.Analysis"></span><code style="font-size: 0.85em">struct Analysis</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`, `Clone`, `PartialEq`, `Eq`

Byte ranges captured from UTF-8 source after optional redaction, sorted and deduplicated.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `docstrings` | `Vec<Range<usize>>` | Documentation ranges, including language-specific documentation comments. |
| `imports` | `Vec<Range<usize>>` | Import statement ranges retained in outlines. |
| `sigs` | `Vec<Range<usize>>` | Declaration header ranges used by the signatures tier. |
| `skel` | `Vec<Range<usize>>` | Additional ranges retained in the documented skeleton tier. |

### <span id="struct.Source"></span><code style="font-size: 0.85em">struct Source</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Default`

UTF-8 source after optional redaction and language-specific outline ranges.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `bytes` | `Vec<u8>` | Source bytes. Keep these valid UTF-8 and aligned with captured ranges. |
| `analysis` | `Option<Analysis>` | Outline ranges, or `None` when no language parser was applied. |

### <span id="struct.Repository"></span><code style="font-size: 0.85em">struct Repository</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Default`

Source files and shared per-language dependency analysis.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `sources` | `ArenaMap<FileId, Source>` | Readable sources keyed by file IDs from the associated index.<br>Oversized, binary, and non-UTF-8 files have no source entry. |
| `analyses` | `HashMap<&'static str, Box<dyn LanguageAnalysis>>` | Per-language dependency state keyed by registered language IDs. |

### <span id="struct.RepositoryReader"></span><code style="font-size: 0.85em">struct RepositoryReader</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Reads bounded source files and redacts recognized secrets before parsing.

#### Methods

##### <span id="RepositoryReader.new"></span><code>new</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn new() -> Self
```

Creates a reader with the built-in secret detection rules.

<details>
<summary>Source</summary>

```rust
    pub fn new() -> Self {
        Self {
            redactor: Redactor::only(&[
                Kind::AwsAccessKey,
                Kind::AzureConnectionString,
                Kind::DiscordToken,
                Kind::GitHubToken,
                Kind::GoogleApiKey,
                Kind::Jwt,
                Kind::OpenAiKey,
                Kind::PrivateKey,
                Kind::SlackToken,
                Kind::StripeKey,
                Kind::TelegramToken,
                Kind::UrlCredentials,
            ]),
        }
    }
```

</details>

##### <span id="RepositoryReader.read"></span><code>read</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn read(
    &self,
    index: &Index,
    config: &Config,
) -> Result<Repository, Error>
```

Reads indexed files, skipping oversized, binary, and non-UTF-8 sources.

**Errors:**

Returns an error if a file cannot be read or language analysis fails.

<details>
<summary>Source</summary>

```rust
    pub fn read(&self, index: &Index, config: &Config) -> Result<Repository, Error> {
        let limit = config.max_file_size_bytes.get();
        let queries: HashMap<_, _> = index
            .languages
            .iter()
            .map(|(&id, language)| Ok((id, language.query()?)))
            .collect::<Result<_, Error>>()?;

        let analyses: HashMap<_, _> = index
            .languages
            .iter()
            .map(|(&id, language)| (id, language.create_analysis()))
            .collect();

        let read_file = |parser: &mut ts::Parser, (file_id, file): (FileId, &File)| {
            let path = index.root.join(&file.path);
            let mut bytes = Vec::new();
            fs::File::open(&path)
                .and_then(|file| {
                    file.take((limit as u64).saturating_add(1))
                        .read_to_end(&mut bytes)
                })
                .map_err(|source| Error::Io { path, source })?;

            if bytes.len() > limit
                || bytes
                    .iter()
                    .any(|&byte| matches!(byte, 0..=8 | 11 | 14..=31))
            {
                return Ok(None);
            }

            let Ok(text) = std::str::from_utf8(&bytes) else {
                return Ok(None);
            };

            if config.redact_secrets {
                let matches = self.redactor.find(text);

                for matched in matches {
                    for byte in &mut bytes[matched.start..matched.end] {
                        if !matches!(*byte, b'\r' | b'\n') {
                            *byte = b'x';
                        }
                    }
                }
            }

            let analysis = file
                .language
                .map(|id| {
                    index.languages[id].analyze(
                        file_id,
                        parser,
                        &queries[id],
                        &bytes,
                        analyses[id].as_ref(),
                    )
                })
                .transpose()?;

            Ok(Some((file_id, Source { bytes, analysis })))
        };

        let sources = if config.enable_parallel {
            let files: Vec<_> = index.files.iter().collect();
            let results: Vec<_> = files
                .into_par_iter()
                .map_init(ts::Parser::new, read_file)
                .collect::<Result<_, Error>>()?;
            results.into_iter().flatten().collect()
        } else {
            let mut parser = ts::Parser::new();
            index
                .files
                .iter()
                .filter_map(|file| read_file(&mut parser, file).transpose())
                .collect::<Result<_, Error>>()?
        };

        Ok(Repository { sources, analyses })
    }
```

</details>
