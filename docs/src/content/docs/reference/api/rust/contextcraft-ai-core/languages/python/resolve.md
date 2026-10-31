---
title: "contextcraft-ai-core::languages::python::resolve"
description: "Resolve captured references to indexed local files."
editUrl: false
sidebar:
  order: 52
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
    packages: &ArenaMap<PackageId, PythonPackage>,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)>
```

Resolves imports through visible local packages and configured source roots.

Includes package initializers and handles namespace packages. Ambiguous
external package ownership is not resolved. Returns sorted, deduplicated edges.

<details>
<summary>Source</summary>

```rust
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, PythonPackage>,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)> {
    let modules = ModuleIndex::new(index, packages);
    let mut visibility = HashMap::new();

    for (id, _) in packages.iter() {
        let mut visible = HashSet::from([id]);
        let mut pending = vec![id];

        while let Some(package) = pending.pop() {
            for dependency in &index.packages[package].dependencies {
                if packages.get(dependency.package).is_some() && visible.insert(dependency.package)
                {
                    pending.push(dependency.package);
                }
            }
        }

        let roots: Vec<_> = modules
            .roots
            .iter()
            .enumerate()
            .filter_map(|(root, (owner, _))| visible.contains(owner).then_some(root))
            .collect();
        visibility.insert(id, roots);
    }

    let mut edges = Vec::new();

    for (file, imports) in imports.iter() {
        let owner = index.files[file].package_id;
        let Some(visible) = visibility.get(&owner) else {
            continue;
        };

        for import in imports {
            for mut name in modules.import_names(file, import) {
                let Some(base) = modules.find(&name, visible, owner) else {
                    continue;
                };

                let mut targets = base.files;

                if import.from && !import.wildcard && base.is_package {
                    let prefix_len = name.len();

                    for imported in &import.names {
                        name.truncate(prefix_len);
                        name.extend(imported.path.iter().map(String::as_str));

                        if let Some(resolved) = modules.find(&name, visible, owner) {
                            targets.extend(resolved.files);
                        }
                    }
                }

                for target in targets {
                    if target != file {
                        edges.push((file, target));
                    }
                }
            }
        }
    }

    edges.sort_unstable();
    edges.dedup();
    edges
}
```

</details>
