---
title: "contextcraft-ai-core::languages::c::dependencies"
description: "Extract dependency references from captured syntax nodes."
editUrl: false
sidebar:
  order: 15
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Extract dependency references from captured syntax nodes.

## Functions

### <span id="fn.extract"></span><code style="font-size: 0.85em">fn extract</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn extract(node: Node<'_>, source: &[u8], includes: &mut Vec<String>)
```

Appends quoted include paths captured by `node`.

Ignores system includes, malformed nodes, and nonliteral paths.

<details>
<summary>Source</summary>

```rust
pub fn extract(node: Node<'_>, source: &[u8], includes: &mut Vec<String>) {
    if node.kind() != "preproc_include" || node.has_error() {
        return;
    }

    let Some(path) = node.child_by_field_name("path") else {
        return;
    };

    if path.kind() == "system_lib_string" {
        if let Ok(value) = path.utf8_text(source) {
            includes.push(value.to_owned());
        }
        return;
    }
    if path.kind() != "string_literal" {
        return;
    }

    if let Ok(text) = path.utf8_text(source)
        && let Some(path) = text
            .strip_prefix('"')
            .and_then(|text| text.strip_suffix('"'))
        && !path.is_empty()
    {
        // Header names are not C string escapes; only preprocessing line splices apply.
        includes.push(path.replace("\\\r\n", "").replace("\\\n", ""));
    }
}
```

</details>
