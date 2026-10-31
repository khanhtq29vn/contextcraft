---
title: "contextcraft-ai-core::languages::go::manifest"
description: "Discover local package metadata and workspace relationships."
editUrl: false
sidebar:
  order: 29
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Discover local package metadata and workspace relationships.

## Structs

### <span id="struct.GoPackage"></span><code style="font-size: 0.85em">struct GoPackage</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Local module build contexts visible to one Go package.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `modules` | `Vec<(String, PackageId)>` | Visible module paths paired with their indexed local package IDs. |

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<(PackageResolution, ArenaMap<PackageId, GoPackage>), Error>
```

Discovers Go modules, workspaces, and local replacement dependencies.

Oversized manifests are skipped according to the configured file size limit.

**Errors:**

Returns an error if manifests cannot be read or parsed, or workspace
membership and dependency configuration are invalid.

<details>
<summary>Source</summary>

```rust
pub fn discover(
    index: &Index,
    config: &Config,
) -> Result<(PackageResolution, ArenaMap<PackageId, GoPackage>), Error> {
    let mut documents = BTreeMap::new();
    let mut resolution = PackageResolution::default();

    for (id, package) in index.packages.iter() {
        if package.language != Some("go") {
            continue;
        }

        let manifest = package.root.join("go.mod");
        let Some(document) = read(index, &manifest, config)? else {
            continue;
        };
        let Some(name) = &document.module else {
            return Err(Error::Manifest {
                path: manifest,
                message: "missing module directive".into(),
            });
        };
        let mut package = package.clone();
        package.name = Some(name.clone());
        resolution.packages.insert(id, package);
        documents.insert(id, document);
    }

    let roots: BTreeMap<_, _> = documents
        .keys()
        .map(|&id| (index.packages[id].root.as_path(), id))
        .collect();
    let mut workspaces = Vec::new();

    for (_, file) in index.files.iter() {
        if file.path.file_name().is_none_or(|name| name != "go.work") {
            continue;
        }

        let Some(document) = read(index, &file.path, config)? else {
            continue;
        };
        let root = file.path.parent().unwrap();
        let mut members: Vec<_> = document
            .uses
            .iter()
            .filter_map(|path| local_path(index, &root.join(path)))
            .filter_map(|path| roots.get(path.as_path()).copied())
            .collect();
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.to_path_buf(),
            language: "go",
            members,
        });
        workspaces.push(document);
    }

    let mut packages = ArenaMap::new();

    for &id in documents.keys() {
        let workspace = resolution
            .workspaces
            .iter()
            .enumerate()
            .filter(|(_, workspace)| workspace.members.contains(&id))
            .max_by_key(|(_, workspace)| workspace.root.components().count());
        let members = workspace
            .map(|(_, workspace)| workspace.members.as_slice())
            .unwrap_or(std::slice::from_ref(&id));
        let mut modules = Vec::new();

        for &member in members {
            modules.push((documents[&member].module.clone().unwrap(), member));
        }

        // Only main modules supply replacements, including for transitive requirements.
        let mut cursor = 0;

        while cursor < modules.len() {
            let document = &documents[&modules[cursor].1];

            for (name, version) in &document.requires {
                if modules.iter().any(|(module, _)| module == name) {
                    continue;
                }

                let workspace_replacement = workspace.and_then(|(position, workspace)| {
                    replacement(&workspaces[position], name, version)
                        .map(|replacement| (replacement, workspace.root.as_path()))
                });
                let candidates: Vec<_> = if let Some(replacement) = workspace_replacement {
                    vec![replacement]
                } else {
                    members
                        .iter()
                        .filter_map(|member| {
                            replacement(&documents[member], name, version).map(|replacement| {
                                (replacement, index.packages[*member].root.as_path())
                            })
                        })
                        .collect()
                };
                let mut targets = Vec::new();

                for (replacement, base) in candidates {
                    let target = replacement
                        .directory
                        .as_ref()
                        .and_then(|path| local_path(index, &base.join(path)))
                        .and_then(|path| roots.get(path.as_path()).copied());
                    targets.push(target);
                }

                targets.sort_unstable();
                targets.dedup();

                // Conflicting replacements must not pick an arbitrary local module.
                if let [Some(target)] = targets.as_slice() {
                    modules.push((name.clone(), *target));
                }
            }

            cursor += 1;
        }

        resolution.packages[id].dependencies = modules
            .iter()
            .filter(|(_, target)| *target != id)
            .map(|(alias, target)| PackageDependency {
                alias: alias.clone(),
                package: *target,
            })
            .collect();
        packages.insert(id, GoPackage { modules });
    }

    Ok((resolution, packages))
}
```

</details>
