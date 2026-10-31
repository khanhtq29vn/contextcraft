---
title: "contextcraft-ai-core::languages::swift::manifest"
description: "Static SwiftPM targets, products, and local package dependencies."
editUrl: false
sidebar:
  order: 66
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Static SwiftPM targets, products, and local package dependencies.

## Functions

### <span id="fn.packages"></span><code style="font-size: 0.85em">fn packages</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn packages(
    index: &Index,
    config: &Config,
) -> Result<Vec<Package>, Error>
```

Discovers static SwiftPM package and target roots, plus indexed Xcode projects.

Returns packages in root-path order without executing Swift manifests.

**Errors:**

Returns an error if a Swift manifest cannot be read, is not UTF-8, or cannot be
parsed, or if targets have duplicate names or share a source directory.
Files exceeding the configured size limit are skipped.

<details>
<summary>Source</summary>

```rust
pub fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "Package.swift")
    }) {
        let Some(manifest) = read(index, &file.path, config)? else {
            continue;
        };
        let root = file.path.parent().unwrap().to_path_buf();
        let mut package = local::package(root.clone(), "swift", file.path.clone());
        package.name = manifest.name;
        packages.insert(root, package);
        let mut target_roots = HashMap::new();
        let mut target_names = std::collections::HashSet::new();
        for target in manifest.targets {
            if !target_names.insert(target.name.clone()) {
                return Err(Error::Manifest {
                    path: file.path.clone(),
                    message: "duplicate Swift target name".into(),
                });
            }
            if target_roots
                .insert(target.root.clone(), target.name.clone())
                .is_some()
            {
                return Err(Error::Manifest {
                    path: file.path.clone(),
                    message:
                        "Swift targets sharing a source directory have ambiguous file ownership"
                            .into(),
                });
            }
            let package = packages.entry(target.root.clone()).or_insert_with(|| {
                let mut package = local::package(target.root, "swift", file.path.clone());
                package.manifests.clear();
                package
            });
            package.name = Some(target.name);
        }
    }
    for project in super::xcode::packages(index) {
        if let Some(package) = packages.get_mut(&project.root) {
            package.manifests.extend(project.manifests);
        } else {
            packages.insert(project.root.clone(), project);
        }
    }
    Ok(packages.into_values().collect())
}
```

</details>

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Resolves indexed SwiftPM and Xcode source targets, local dependencies, and workspaces.

Package IDs refer to `index`; discover and assign packages before calling this function.
Swift manifests are analyzed statically, not executed.

**Errors:**

Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
cannot be created, or if an Xcode project or workspace cannot be parsed.
Files exceeding the configured size limit are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut documents = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "Package.swift")
    }) {
        if let Some(manifest) = read(index, &file.path, config)? {
            documents.insert(file.path.parent().unwrap().to_path_buf(), manifest);
        }
    }
    let roots: BTreeMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("swift"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    let mut resolution = PackageResolution::default();
    for &id in roots.values() {
        resolution.packages.insert(id, index.packages[id].clone());
    }

    for (root, manifest) in &documents {
        let mut members = Vec::new();
        if let Some(&id) = roots.get(root.as_path()) {
            members.push(id);
        }
        for target in &manifest.targets {
            let Some(&id) = roots.get(target.root.as_path()) else {
                continue;
            };
            members.push(id);
            let package = &mut resolution.packages[id];
            package.targets = index
                .files
                .iter()
                .filter(|(_, file)| {
                    file.language == Some("swift")
                        && file.package_id == id
                        && !file.path.ends_with("Package.swift")
                        && !target
                            .exclude
                            .iter()
                            .any(|path| file.path.starts_with(target.root.join(path)))
                        && target.sources.as_ref().is_none_or(|sources| {
                            sources
                                .iter()
                                .any(|path| file.path.starts_with(target.root.join(path)))
                        })
                })
                .map(|(id, _)| id)
                .collect();

            for (name, identity) in &target.dependencies {
                let mut targets = Vec::new();
                if identity.is_none() {
                    targets.extend(
                        manifest
                            .targets
                            .iter()
                            .filter(|target| target.name == *name)
                            .filter_map(|target| roots.get(target.root.as_path()).copied()),
                    );
                }
                if targets.is_empty() {
                    for (alias, path) in &manifest.paths {
                        let Some(dependency) = documents.get(path) else {
                            continue;
                        };
                        if identity.as_ref().is_some_and(|identity| {
                            alias.as_ref().is_none_or(|alias| alias != identity)
                                && path.file_name().is_none_or(|name| {
                                    !name.to_string_lossy().eq_ignore_ascii_case(identity)
                                })
                        }) {
                            continue;
                        }
                        if let Some(names) = dependency.products.get(name) {
                            targets.extend(
                                dependency
                                    .targets
                                    .iter()
                                    .filter(|target| names.contains(&target.name))
                                    .filter_map(|target| roots.get(target.root.as_path()).copied()),
                            );
                        }
                    }
                }
                for dependency in targets {
                    if dependency != id {
                        package.dependencies.push(PackageDependency {
                            alias: name.clone(),
                            package: dependency,
                        });
                    }
                }
            }
        }
        for (_, path) in &manifest.paths {
            if let Some(&id) = roots.get(path.as_path()) {
                members.push(id);
            }
        }
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.clone(),
            language: "swift",
            members,
        });
    }
    super::xcode::discover(index, config, &mut resolution)?;
    Ok(resolution)
}
```

</details>
