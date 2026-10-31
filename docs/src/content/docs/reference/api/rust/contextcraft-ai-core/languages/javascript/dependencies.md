---
title: "contextcraft-ai-core::languages::javascript::dependencies"
description: "Extract dependency references from captured syntax nodes."
editUrl: false
sidebar:
  order: 35
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Extract dependency references from captured syntax nodes.

## Structs

### <span id="struct.Import"></span><code style="font-size: 0.85em">struct Import</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Literal module reference extracted from JavaScript or TypeScript.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `path` | `String` | Decoded module specifier. |
| `kind` | `ImportKind` | Module-loading syntax that produced this reference. |

## Enums

### <span id="enum.ImportKind"></span><code style="font-size: 0.85em">enum ImportKind</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Module-loading syntax used to choose relative path resolution rules.

#### Variants

- **`Module`** - ECMAScript import or re-export, including dynamic `import()`.
- **`Require`** - CommonJS `require()` or TypeScript import assignment.

## Functions

### <span id="fn.extract"></span><code style="font-size: 0.85em">fn extract</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>)
```

Appends literal imports, re-exports, and supported module-loading calls.

Ignores malformed nodes and paths that are not string literals.

<details>
<summary>Source</summary>

```rust
pub fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>) {
    if node.has_error() {
        return;
    }

    let (path, kind) = match node.kind() {
        "import_statement" | "export_statement" => {
            (node.child_by_field_name("source"), ImportKind::Module)
        }
        "import_require_clause" => (node.child_by_field_name("source"), ImportKind::Require),
        "call_expression" => {
            let Some(function) = node.child_by_field_name("function") else {
                return;
            };
            let kind = if function.kind() == "import" {
                ImportKind::Module
            } else if function.kind() == "identifier"
                && function.utf8_text(source) == Ok("require")
                && node.child_by_field_name("optional_chain").is_none()
            {
                ImportKind::Require
            } else {
                return;
            };
            let Some(arguments) = node.child_by_field_name("arguments") else {
                return;
            };
            let mut cursor = arguments.walk();
            let mut arguments = arguments
                .named_children(&mut cursor)
                .filter(|argument| argument.kind() != "comment");
            let path = arguments.next();

            if kind == ImportKind::Require && arguments.next().is_some() {
                return;
            }

            (path, kind)
        }
        _ => return,
    };

    if let Some(path) = path
        && path.kind() == "string"
        && let Some(path) = path.utf8_text(source).ok().and_then(unquote)
    {
        imports.push(Import { path, kind });
    }
}
```

</details>
