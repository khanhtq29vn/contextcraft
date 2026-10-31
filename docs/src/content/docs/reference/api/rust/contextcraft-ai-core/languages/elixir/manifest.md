---
title: "contextcraft-ai-core::languages::elixir::manifest"
description: "Literal Mix application names, path dependencies, and umbrella membership."
editUrl: false
sidebar:
  order: 26
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Literal Mix application names, path dependencies, and umbrella membership.

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Resolves literal Mix path dependencies and umbrella application membership.

Only simple zero-argument helpers returning literal lists are followed. Mix
code is never executed; remote dependencies and dynamic expressions are ignored.

**Errors:**

Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
cannot be created. Oversized and syntactically malformed manifests are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut documents = HashMap::new();
    let roots: HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("elixir"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    for &id in roots.values() {
        let mut package = index.packages[id].clone();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| file.package_id == id && file.language == Some("elixir"))
            .map(|(id, _)| id)
            .collect();
        if let Some(manifest) = package
            .manifests
            .iter()
            .find(|path| path.file_name().is_some_and(|name| name == "mix.exs"))
            && let Some(document) = read(index, manifest, config)?
        {
            package.name = document.app.clone();
            documents.insert(id, document);
        }
        resolution.packages.insert(id, package);
    }
    let mut umbrellas: HashMap<PackageId, Vec<PackageId>> = HashMap::new();
    for (&id, document) in &documents {
        let Some(path) = &document.apps_path else {
            continue;
        };
        let mut members: Vec<_> = documents
            .iter()
            .filter(|(member, app)| {
                index.packages[**member].root.parent() == Some(path.as_path())
                    && document
                        .apps
                        .as_ref()
                        .is_none_or(|apps| app.app.as_ref().is_some_and(|name| apps.contains(name)))
            })
            .map(|(&id, _)| id)
            .collect();
        members.sort_unstable();
        umbrellas.insert(id, members.clone());
        members.push(id);
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: index.packages[id].root.clone(),
            language: "elixir",
            members,
        });
    }
    resolution.workspaces.sort_by(|a, b| a.root.cmp(&b.root));
    for (&id, document) in &documents {
        for (alias, path) in &document.dependencies {
            let target = if let Some(path) = path {
                roots.get(path.as_path()).copied()
            } else {
                let mut candidates = umbrellas
                    .values()
                    .filter(|members| members.contains(&id))
                    .flatten()
                    .copied()
                    .filter(|target| documents[target].app.as_ref() == Some(alias));
                let first = candidates.next();
                if candidates.next().is_some() {
                    None
                } else {
                    first
                }
            };
            if let Some(target) = target
                && target != id
                && resolution.packages[target]
                    .name
                    .as_ref()
                    .is_none_or(|name| name == alias)
            {
                let dependency = PackageDependency {
                    alias: alias.clone(),
                    package: target,
                };
                if !resolution.packages[id].dependencies.contains(&dependency) {
                    resolution.packages[id].dependencies.push(dependency);
                }
            }
        }
    }
    Ok(resolution)
}
```

</details>
