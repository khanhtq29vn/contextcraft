---
title: "contextcraft-ai-core::tokens"
description: "Count ordinary text tokens with the configured tokenizer vocabulary."
editUrl: false
sidebar:
  order: 77
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Count ordinary text tokens with the configured tokenizer vocabulary.

## Structs

### <span id="struct.TokenCounter"></span><code style="font-size: 0.85em">struct TokenCounter</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Exact token counter backed by a shared tokenizer vocabulary.

#### Methods

##### <span id="TokenCounter.new"></span><code>new</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn new(
    encoding: TokenizerEncoding,
    _allow_estimates: bool,
) -> Result<Self, Error>
```

Creates a counter for the selected vocabulary.

`allow_estimates` is reserved for fallback counting. This implementation
always uses exact counts.

**Errors:**

Returns an error if the vocabulary is unavailable.

<details>
<summary>Source</summary>

```rust
    pub fn new(encoding: TokenizerEncoding, _allow_estimates: bool) -> Result<Self, Error> {
        let encoder =
            tiktoken::get_encoding(encoding.as_str()).ok_or_else(|| Error::Tokenization {
                encoding: encoding.as_str(),
                message: "encoding is not available".into(),
            })?;

        Ok(Self { encoder })
    }
```

</details>

##### <span id="TokenCounter.count"></span><code>count</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn count(&self, content: &str) -> Result<usize, Error>
```

Returns the token count, treating special-token markers as ordinary text.

**Errors:**

This implementation always succeeds once the vocabulary is loaded.

<details>
<summary>Source</summary>

```rust
    pub fn count(&self, content: &str) -> Result<usize, Error> {
        Ok(self.encoder.count(content))
    }
```

</details>

##### <span id="TokenCounter.used_estimates"></span><code>used_​estimates</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn used_estimates(&self) -> bool
```

Returns whether fallback estimates were used. Currently always `false`.

<details>
<summary>Source</summary>

```rust
    pub fn used_estimates(&self) -> bool {
        false
    }
```

</details>
