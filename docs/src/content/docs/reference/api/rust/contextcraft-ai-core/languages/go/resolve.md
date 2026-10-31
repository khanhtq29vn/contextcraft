---
title: "contextcraft-ai-core::languages::go::resolve"
description: "Resolve captured references to indexed local files."
editUrl: false
sidebar:
  order: 30
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
    packages: &ArenaMap<PackageId, GoPackage>,
    dependencies: &ArenaMap<FileId, Dependencies>,
) -> Vec<(FileId, FileId)>
```

Resolves imports and same-package file dependencies across local modules.

Includes possible local build contexts without evaluating build tags.
Returns sorted, deduplicated edges.

<details>
<summary>Source</summary>

```rust
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, GoPackage>,
    dependencies: &ArenaMap<FileId, Dependencies>,
) -> Vec<(FileId, FileId)> {
    let mut contexts: HashMap<_, Vec<_>> = HashMap::new();

    // Replacement modules use the main module's build list, not their own replacements.
    for (owner, package) in packages.iter() {
        let mut members: Vec<_> = package.modules.iter().map(|(_, member)| *member).collect();
        members.sort_unstable();
        members.dedup();

        for member in members {
            contexts.entry(member).or_default().push(owner);
        }
    }

    let mut directories: HashMap<_, Vec<_>> = HashMap::new();

    for (file, dependency) in dependencies.iter() {
        let source = &index.files[file];

        if dependency.package.is_some() && !ignored_file(&source.path) {
            directories
                .entry((source.package_id, source.path.parent().unwrap()))
                .or_default()
                .push(file);
        }
    }

    let mut edges = Vec::new();

    for (file, dependency) in dependencies.iter() {
        let source = &index.files[file];

        if ignored_file(&source.path) {
            continue;
        }

        let directory = source.path.parent().unwrap();
        let is_test = test_file(&source.path);

        if let Some(peers) = directories.get(&(source.package_id, directory)) {
            for &peer in peers {
                let same_package = dependency.package == dependencies[peer].package;
                let internal_package = is_test
                    && !test_file(&index.files[peer].path)
                    && dependency
                        .package
                        .as_deref()
                        .and_then(|name| name.strip_suffix("_test"))
                        == dependencies[peer].package.as_deref();

                if peer != file
                    && (same_package || internal_package)
                    && (is_test || !test_file(&index.files[peer].path))
                {
                    edges.push((file, peer));
                }
            }
        }

        let Some(contexts) = contexts.get(&source.package_id) else {
            continue;
        };

        for &context in contexts {
            let package = &packages[context];

            for import in &dependency.imports {
                let Some((module, target)) = package
                    .modules
                    .iter()
                    .filter(|(module, _)| {
                        import == module
                            || import
                                .strip_prefix(module.as_str())
                                .is_some_and(|suffix| suffix.starts_with('/'))
                    })
                    .max_by_key(|(module, _)| module.len())
                else {
                    continue;
                };
                let suffix = import.strip_prefix(module).unwrap();
                let suffix = suffix.strip_prefix('/').unwrap_or(suffix);

                if !suffix.is_empty()
                    && suffix
                        .split('/')
                        .any(|component| matches!(component, "" | "." | ".."))
                    || suffix.contains('\\')
                {
                    continue;
                }

                let directory = index.packages[*target].root.join(suffix);

                if let Some(targets) = directories.get(&(*target, directory.as_path())) {
                    for &target in targets {
                        if target != file
                            && !test_file(&index.files[target].path)
                            && dependencies[target].package.as_deref() != Some("main")
                        {
                            edges.push((file, target));
                        }
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
