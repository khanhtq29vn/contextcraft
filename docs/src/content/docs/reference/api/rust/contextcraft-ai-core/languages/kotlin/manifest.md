---
title: "contextcraft-ai-core::languages::kotlin::manifest"
description: "Literal Gradle project includes, directory mappings, and project dependencies."
editUrl: false
sidebar:
  order: 42
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Literal Gradle project includes, directory mappings, and project dependencies.

Supports Kotlin and Groovy DSL statements without evaluating either language.
Conditional blocks, composite builds, plugins, and computed paths are not resolved.
Files containing `${...}` interpolation, escaped multiline strings, or slashy
strings are skipped rather than interpreted.

## Functions

### <span id="fn.packages"></span><code style="font-size: 0.85em">fn packages</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn packages(
    index: &Index,
    config: &Config,
) -> Result<Vec<Package>, Error>
```

Discovers Gradle build roots and literal included projects before file ownership is assigned.

Supports `include`, `rootProject.name`, and `project(...).projectDir = file(...)`.
Computed directory overrides are not replaced with guessed default directories.

**Errors:**

Returns an error if settings cannot be read, are not UTF-8, or multiple project
names in one settings file map to the same local directory. Oversized files are skipped.

<details>
<summary>Source</summary>

```rust
pub fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages: BTreeMap<_, _> =
        local::discover(index, "kotlin", &[], &["build.gradle", "build.gradle.kts"])
            .into_iter()
            .map(|package| (package.root.clone(), package))
            .collect();
    for document in settings(index, config)? {
        let mut seen = HashSet::new();
        for (name, root) in document.projects {
            if !seen.insert(root.clone()) {
                return Err(Error::Manifest {
                    path: document.manifest.clone(),
                    message: "Gradle projects sharing a directory have ambiguous file ownership"
                        .into(),
                });
            }
            let package = packages.entry(root.clone()).or_insert_with(|| Package {
                root,
                name: None,
                language: Some("kotlin"),
                manifests: Vec::new(),
                targets: Vec::new(),
                dependencies: Vec::new(),
            });
            if name == ":" {
                package.name = document.name.clone();
                package.manifests.push(document.manifest.clone());
            } else {
                package.name = name.rsplit(':').next().map(str::to_owned);
            }
        }
    }
    for package in packages.values_mut() {
        package.manifests.sort();
        package.manifests.dedup();
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

Resolves literal Gradle project dependencies and records explicit build membership.

Only known dependency configurations in top-level `dependencies` blocks are
supported. Workspace membership alone does not grant cross-project visibility.

**Errors:**

Returns an error if settings or build files cannot be read or are not UTF-8.
Oversized files and unsupported expressions are skipped without executing Gradle.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let roots: HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("kotlin"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    let mut workspaces = Vec::new();
    for document in settings(index, config)? {
        let projects: BTreeMap<_, _> = document
            .projects
            .into_iter()
            .filter_map(|(name, root)| roots.get(root.as_path()).map(|&id| (name, id)))
            .collect();
        let mut members: Vec<_> = projects.values().copied().collect();
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: document.root,
            language: "kotlin",
            members,
        });
        workspaces.push(projects);
    }
    for &id in roots.values() {
        let mut package = index.packages[id].clone();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| file.package_id == id && file.language == Some("kotlin"))
            .map(|(id, _)| id)
            .collect();
        if let Some(manifest) = package.manifests.iter().find(|path| {
            path.file_name()
                .is_some_and(|name| name == "build.gradle" || name == "build.gradle.kts")
        }) && let Some(source) = local::read(index, manifest, config)?
        {
            for alias in dependencies(&source) {
                let candidates: HashSet<_> = workspaces
                    .iter()
                    .flat_map(|projects| {
                        projects.iter().filter_map(|(name, &member)| {
                            if member != id {
                                return None;
                            }
                            let path = if alias.starts_with(':') {
                                alias.clone()
                            } else {
                                format!("{}:{alias}", name.trim_end_matches(':'))
                            };
                            projects.get(&path).copied()
                        })
                    })
                    .collect();
                if candidates.len() == 1 {
                    let target = *candidates.iter().next().unwrap();
                    if target != id {
                        package.dependencies.push(PackageDependency {
                            alias,
                            package: target,
                        });
                    }
                }
            }
        }
        resolution.packages.insert(id, package);
    }
    Ok(resolution)
}
```

</details>
