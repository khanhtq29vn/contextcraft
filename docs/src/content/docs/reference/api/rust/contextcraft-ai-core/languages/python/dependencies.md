---
title: "contextcraft-ai-core::languages::python::dependencies"
description: "Extract dependency references from captured syntax nodes."
editUrl: false
sidebar:
  order: 50
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Extract dependency references from captured syntax nodes.

## Structs

### <span id="struct.Import"></span><code style="font-size: 0.85em">struct Import</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

One Python module import or `from` import statement.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `module` | `Vec<String>` | Module path components, without relative-import dots. |
| `level` | `usize` | Number of leading dots. Zero denotes an absolute import. |
| `alias` | `Option<String>` | Explicit alias of a direct module import, if present. |
| `names` | `Vec<ImportedName>` | Names imported by a `from` statement. |
| `from` | `bool` | Whether this reference came from a `from` statement. |
| `wildcard` | `bool` | Whether the statement imports `*` rather than named members. |

### <span id="struct.ImportedName"></span><code style="font-size: 0.85em">struct ImportedName</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

One name and optional alias in a Python import statement.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `path` | `Vec<String>` | Imported name split into dotted path components. |
| `alias` | `Option<String>` | Explicit local alias, if present. |

## Functions

### <span id="fn.extract"></span><code style="font-size: 0.85em">fn extract</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>)
```

Appends imports and imported names captured from a Python statement.

Ignores malformed nodes. Relative imports retain their leading-dot count.

<details>
<summary>Source</summary>

```rust
pub fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>) {
    if node.has_error() {
        return;
    }

    let mut cursor = node.walk();
    let names: Vec<_> = node
        .children_by_field_name("name", &mut cursor)
        .map(|name| imported_name(name, source))
        .collect();

    if node.kind() == "import_statement" {
        for name in names {
            imports.push(Import {
                module: name.path,
                level: 0,
                alias: name.alias,
                names: Vec::new(),
                from: false,
                wildcard: false,
            });
        }
    } else if node.kind() == "import_from_statement" {
        let Some(module) = node.child_by_field_name("module_name") else {
            return;
        };

        let mut level = 0;
        let mut path = Vec::new();

        if module.kind() == "relative_import" {
            let mut cursor = module.walk();

            for child in module.named_children(&mut cursor) {
                match child.kind() {
                    "import_prefix" => {
                        level = child
                            .utf8_text(source)
                            .unwrap_or("")
                            .chars()
                            .filter(|&c| c == '.')
                            .count()
                    }

                    "dotted_name" => path = dotted_name(child, source),
                    _ => {}
                }
            }
        } else {
            path = dotted_name(module, source);
        }

        let mut cursor = node.walk();
        let wildcard = node
            .named_children(&mut cursor)
            .any(|child| child.kind() == "wildcard_import");

        imports.push(Import {
            module: path,
            level,
            alias: None,
            names,
            from: true,
            wildcard,
        });
    }
}
```

</details>
