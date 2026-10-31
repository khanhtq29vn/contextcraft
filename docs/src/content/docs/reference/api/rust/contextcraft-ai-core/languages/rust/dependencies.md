---
title: "contextcraft-ai-core::languages::rust::dependencies"
description: "Extract dependency references from captured syntax nodes."
editUrl: false
sidebar:
  order: 57
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Extract dependency references from captured syntax nodes.

## Structs

### <span id="struct.RustDependencies"></span><code style="font-size: 0.85em">struct RustDependencies</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`, `Clone`, `PartialEq`, `Eq`

Module declarations and imports extracted from one Rust source file.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `modules` | `Vec<ModuleDeclaration>` | Module declarations in capture order. |
| `imports` | `Vec<Import>` | Expanded imports in capture order. |
| `includes` | `Vec<String>` | Literal include!, include_str!, and include_bytes! paths. |

### <span id="struct.ModuleDeclaration"></span><code style="font-size: 0.85em">struct ModuleDeclaration</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

A module declaration with its enclosing context and path attributes.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `context` | `Vec<String>` | Enclosing inline module names, from outermost to innermost. |
| `name` | `String` | Declared module name, without a raw identifier prefix. |
| `inline` | `bool` | Whether the module body is defined in this source file. |
| `path_override` | `Option<PathBuf>` | Literal path from a recognized `#[path]` attribute, if present. |
| `unresolved_path` | `bool` | Whether conflicting or unsupported path attributes prevent resolution. |
| `test_only` | `bool` | Whether this declaration or an ancestor has a direct `#[cfg(test)]` guard. |

### <span id="struct.Import"></span><code style="font-size: 0.85em">struct Import</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

An expanded Rust import with lexical context and resolution flags.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `context` | `Vec<String>` | Enclosing inline module names, from outermost to innermost. |
| `path` | `Vec<String>` | Import path components, without raw identifier prefixes. |
| `alias` | `Option<String>` | Explicit local alias, if present. |
| `glob` | `bool` | Whether the import ends in a wildcard. |
| `public` | `bool` | Whether the declaration has an explicit visibility modifier. |
| `absolute` | `bool` | Whether the path is absolute or comes from `extern crate`. |
| `external` | `bool` | Whether this is an `extern crate` declaration. |
| `module_level` | `bool` | Whether the import is declared directly in a module scope. |
| `test_only` | `bool` | Whether this import or an ancestor has a direct `#[cfg(test)]` guard. |

## Functions

### <span id="fn.extract"></span><code style="font-size: 0.85em">fn extract</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn extract(
    node: Node<'_>,
    source: &[u8],
    dependencies: &mut RustDependencies,
)
```

Appends module declarations and expanded imports from a captured node.

Retains enclosing module context, aliases, and directly recognized test guards.

<details>
<summary>Source</summary>

```rust
pub fn extract(node: Node<'_>, source: &[u8], dependencies: &mut RustDependencies) {
    if node.has_error() {
        return;
    }

    if node.kind() == "macro_invocation" {
        let mut cursor = node.walk();
        if let Some(tokens) = node
            .named_children(&mut cursor)
            .find(|node| node.kind() == "token_tree")
        {
            let mut cursor = tokens.walk();
            let arguments: Vec<_> = tokens.named_children(&mut cursor).collect();
            if let [argument] = arguments.as_slice()
                && let Some(path) = string(*argument, source)
                && !path.contains('\0')
                && !std::path::Path::new(&path).is_absolute()
            {
                dependencies.includes.push(path);
            }
        }
        return;
    }

    let mut context = Vec::new();
    let mut module_level = true;
    let mut parent = node.parent();

    while let Some(ancestor) = parent {
        if ancestor.kind() == "mod_item" {
            if let Some(name) = ancestor.child_by_field_name("name") {
                context.push(text(name, source));
            }
        } else if !matches!(ancestor.kind(), "source_file" | "declaration_list") {
            module_level = false;
        }

        parent = ancestor.parent();
    }

    context.reverse();

    match node.kind() {
        "mod_item" if module_level => {
            let Some(name) = node.child_by_field_name("name") else {
                return;
            };

            let mut path_override = None;
            let mut unresolved_path = false;
            let mut previous = node.prev_named_sibling();

            while let Some(attribute_item) = previous {
                if matches!(attribute_item.kind(), "line_comment" | "block_comment") {
                    previous = attribute_item.prev_named_sibling();
                    continue;
                }

                if attribute_item.kind() != "attribute_item" {
                    break;
                }

                if let Some(attribute) = attribute_item.named_child(0)
                    && let Some(name) = attribute.named_child(0)
                {
                    if text(name, source) == "path" {
                        let path = attribute
                            .child_by_field_name("value")
                            .and_then(|value| string(value, source));

                        if path_override.is_some() || path.is_none() {
                            unresolved_path = true;
                        }

                        path_override = path.map(PathBuf::from);
                    } else if text(name, source) == "cfg_attr"
                        && attribute.utf8_text(source).unwrap_or("").contains("path")
                    {
                        unresolved_path = true;
                    }
                }

                previous = attribute_item.prev_named_sibling();
            }

            dependencies.modules.push(ModuleDeclaration {
                context,
                name: text(name, source),
                inline: node.child_by_field_name("body").is_some(),
                path_override,
                unresolved_path,
                test_only: test_only(node, source),
            });
        }

        "use_declaration" => {
            let Some(argument) = node.child_by_field_name("argument") else {
                return;
            };

            let mut cursor = node.walk();
            let public = node
                .named_children(&mut cursor)
                .any(|child| child.kind() == "visibility_modifier");
            let template = Import {
                context,
                path: Vec::new(),
                alias: None,
                glob: false,
                public,
                absolute: argument.utf8_text(source).unwrap_or("").starts_with("::"),
                external: false,
                module_level,
                test_only: test_only(node, source),
            };

            expand(argument, source, &[], &template, &mut dependencies.imports);
        }

        "extern_crate_declaration" => {
            let Some(name) = node.child_by_field_name("name") else {
                return;
            };

            dependencies.imports.push(Import {
                context,
                path: vec![text(name, source)],
                alias: node
                    .child_by_field_name("alias")
                    .map(|alias| text(alias, source)),
                glob: false,
                public: node
                    .utf8_text(source)
                    .unwrap_or("")
                    .trim_start()
                    .starts_with("pub"),
                absolute: true,
                external: true,
                module_level,
                test_only: test_only(node, source),
            });
        }

        _ => {}
    }
}
```

</details>
