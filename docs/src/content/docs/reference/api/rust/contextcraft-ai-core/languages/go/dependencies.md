---
title: "contextcraft-ai-core::languages::go::dependencies"
description: "Extract dependency references from captured syntax nodes."
editUrl: false
sidebar:
  order: 28
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Extract dependency references from captured syntax nodes.

## Structs

### <span id="struct.Dependencies"></span><code style="font-size: 0.85em">struct Dependencies</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Package name and literal imports extracted from one Go source file.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `package` | `Option<String>` | Declared package name, if captured successfully. |
| `imports` | `Vec<String>` | Decoded import paths in capture order. |
| `embeds` | `Vec<String>` | Static go:embed patterns. |

## Functions

### <span id="fn.extract"></span><code style="font-size: 0.85em">fn extract</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn extract(
    node: Node<'_>,
    source: &[u8],
    dependencies: &mut Dependencies,
)
```

Records a package clause or appends an import path from a captured node.

Ignores malformed nodes and unrecognized import string escapes.

<details>
<summary>Source</summary>

```rust
pub fn extract(node: Node<'_>, source: &[u8], dependencies: &mut Dependencies) {
    if node.has_error() {
        return;
    }

    if node.kind() == "comment" {
        if let Some(raw) = node
            .utf8_text(source)
            .ok()
            .and_then(|text| text.strip_prefix("//go:embed"))
        {
            let pattern = regex::Regex::new(r#""(?:[^"\\]|\\.)*"|`[^`]*`|[^\s]+"#).unwrap();
            for value in pattern.find_iter(raw).map(|value| value.as_str()) {
                if let Some(value) = if value.starts_with(['"', '`']) {
                    unquote(value)
                } else {
                    Some(value.to_owned())
                } {
                    dependencies.embeds.push(value);
                }
            }
        }
    } else if node.kind() == "package_clause" {
        let mut cursor = node.walk();
        dependencies.package = node
            .named_children(&mut cursor)
            .find(|child| child.kind() == "package_identifier")
            .and_then(|name| name.utf8_text(source).ok())
            .map(str::to_owned);
    } else if let Some(path) = node.child_by_field_name("path")
        && let Some(path) = path.utf8_text(source).ok().and_then(unquote)
    {
        dependencies.imports.push(path);
    }
}
```

</details>
