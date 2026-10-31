---
title: "contextcraft-ai-core::languages::rust::resolve"
description: "Resolve captured references to indexed local files."
editUrl: false
sidebar:
  order: 59
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Resolve captured references to indexed local files.

## Functions

### <span id="fn.resolve"></span><code style="font-size: 0.85em">fn resolve</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, RustPackage>,
    dependencies: &ArenaMap<FileId, RustDependencies>,
) -> Vec<(FileId, FileId)>
```

Resolves module declarations and imports within discovered Cargo targets.

Resolves module aliases to a fixed point. Ambiguous module paths are not
assigned an arbitrary target. Returned edges may contain duplicates.

<details>
<summary>Source</summary>

```rust
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, RustPackage>,
    dependencies: &ArenaMap<FileId, RustDependencies>,
) -> Vec<(FileId, FileId)> {
    let (modules, mut edges) = discover_modules(index, packages, dependencies);

    let mut lookup = ModuleLookup::new();

    for module in &modules {
        lookup
            .entry(module.key.0)
            .or_default()
            .entry(module.key.1.as_slice())
            .and_modify(|file| {
                if *file != Some(module.file) {
                    *file = None;
                }
            })
            .or_insert(Some(module.file));
    }

    let mut imports = Vec::new();

    for module in &modules {
        if let Some(dependencies) = dependencies.get(module.file) {
            for import in &dependencies.imports {
                if import.context == module.context {
                    imports.push((module, import));
                }
            }
        }
    }

    let mut bindings = HashMap::new();

    // Resolve module aliases to a fixed point, independently of declaration order.
    loop {
        let mut changed = false;

        for &(module, import) in &imports {
            if import.glob || !import.module_level {
                continue;
            }

            let Some((target, true)) = resolve_import(packages, module, import, &lookup, &bindings)
            else {
                continue;
            };

            if unique_file(&target, &lookup).is_none() {
                continue;
            }

            let alias = import
                .alias
                .as_ref()
                .or_else(|| import.path.last())
                .unwrap();

            if alias == "_" {
                continue;
            }

            let scope = (module.key.0, module.key.1.as_slice());
            changed |= bindings
                .entry(scope)
                .or_default()
                .entry(alias.as_str())
                .or_default()
                .insert(target);
        }

        if !changed {
            break;
        }
    }

    for (module, import) in imports {
        if let Some((target, _)) = resolve_import(packages, module, import, &lookup, &bindings)
            && let Some(file) = unique_file(&target, &lookup)
            && file != module.file
        {
            edges.push((module.file, file));
        }
    }

    edges
}
```

</details>
