---
title: "contextcraft-ai-core::languages::scala::manifest"
description: "Literal sbt project roots, dependsOn relationships, and build membership."
editUrl: false
sidebar:
  order: 61
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Literal sbt project roots, dependsOn relationships, and build membership.

## Functions

### <span id="fn.packages"></span><code style="font-size: 0.85em">fn packages</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn packages(
    index: &Index,
    config: &Config,
) -> Result<Vec<Package>, Error>
```

Discovers sbt build roots and literal subproject directories in root-path order.

Does not evaluate sbt. Project directories must resolve within the repository.

**Errors:**

Returns an error if a build file cannot be read, is not UTF-8, or its syntax tree
cannot be created. Files exceeding the configured size limit are skipped.

<details>
<summary>Source</summary>

```rust
pub fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "build.sbt")
    }) {
        let root = file.path.parent().unwrap().to_path_buf();
        packages
            .entry(root.clone())
            .or_insert_with(|| local::package(root, "scala", file.path.clone()));
        for project in projects(index, &file.path, config)? {
            let package = packages.entry(project.root.clone()).or_insert_with(|| {
                let mut package = local::package(project.root, "scala", file.path.clone());
                package.manifests.clear();
                package
            });
            package.name = Some(project.name);
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

Resolves indexed Scala source targets, literal `dependsOn` links, and sbt workspaces.

Package IDs refer to `index`; discover and assign packages before calling this function.

**Errors:**

Returns an error if a build file cannot be read, is not UTF-8, or its syntax tree
cannot be created. Files exceeding the configured size limit are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let roots: BTreeMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("scala"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();

    for &id in roots.values() {
        let mut package = index.packages[id].clone();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| file.package_id == id && file.language == Some("scala"))
            .map(|(file, _)| file)
            .collect();
        resolution.packages.insert(id, package);
    }

    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "build.sbt")
    }) {
        let projects = projects(index, &file.path, config)?;
        let names: BTreeMap<_, _> = projects
            .iter()
            .filter_map(|project| {
                roots
                    .get(project.root.as_path())
                    .map(|&id| (project.name.as_str(), id))
            })
            .collect();
        let mut members: Vec<_> = names.values().copied().collect();
        if let Some(&id) = roots.get(file.path.parent().unwrap()) {
            members.push(id);
        }
        members.sort_unstable();
        members.dedup();
        for project in &projects {
            let Some(&id) = names.get(project.name.as_str()) else {
                continue;
            };
            for dependency in &project.dependencies {
                if let Some(&target) = names.get(dependency.as_str())
                    && target != id
                {
                    resolution.packages[id]
                        .dependencies
                        .push(PackageDependency {
                            alias: dependency.clone(),
                            package: target,
                        });
                }
            }
        }
        resolution.workspaces.push(Workspace {
            root: file.path.parent().unwrap().to_path_buf(),
            language: "scala",
            members,
        });
    }
    Ok(resolution)
}
```

</details>
