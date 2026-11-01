---
title: "contextcraft-ai-core::languages::php::manifest"
description: "Composer names, static autoload roots, and declared local path repositories."
editUrl: false
sidebar:
  order: 53
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Composer names, static autoload roots, and declared local path repositories.

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Reads Composer autoload declarations and links required packages in path repositories.

**Errors:**

Returns an error for unreadable, invalid UTF-8, or malformed JSON manifests.
Oversized files, custom installers, remote packages, and computed paths are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut documents = Vec::new();
    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("php"))
    {
        let Some(manifest) = package.manifests.first() else {
            continue;
        };
        let Some(source) = local::read(index, manifest, config)? else {
            continue;
        };
        let document: Value = serde_json::from_str(&source).map_err(|error| Error::Manifest {
            path: manifest.clone(),
            message: error.to_string(),
        })?;
        if !document.is_object() {
            return Err(Error::Manifest {
                path: manifest.clone(),
                message: "Composer manifest must be an object".into(),
            });
        }
        let mut package = package.clone();
        package.name = document
            .get("name")
            .and_then(Value::as_str)
            .map(str::to_owned);
        for section in ["autoload", "autoload-dev"] {
            let Some(autoload) = document.get(section) else {
                continue;
            };
            let mut roots = Vec::new();
            for kind in ["psr-4", "psr-0"] {
                if let Some(mappings) = autoload.get(kind).and_then(Value::as_object) {
                    for value in mappings.values() {
                        roots.extend(paths(value).into_iter().map(|path| (path, false)));
                    }
                }
            }
            for kind in ["classmap", "files"] {
                if let Some(value) = autoload.get(kind) {
                    roots.extend(
                        paths(value)
                            .into_iter()
                            .map(|path| (path, kind == "classmap")),
                    );
                }
            }
            let exclusions: Vec<_> = autoload
                .get("exclude-from-classmap")
                .map(paths)
                .unwrap_or_default()
                .into_iter()
                .filter_map(|path| local::path_glob(&package.root, path.trim_start_matches('/')))
                .collect();
            for (path, classmap) in roots {
                let root = local_path(index, &package.root.join(path));
                let matcher = local::path_glob(&package.root, path);
                for (file, metadata) in index
                    .files
                    .iter()
                    .filter(|(_, file)| file.package_id == id && file.language == Some("php"))
                {
                    if (root
                        .as_ref()
                        .is_some_and(|root| metadata.path.starts_with(root))
                        || matcher.as_ref().is_some_and(|matcher| {
                            metadata.path.ancestors().any(|path| matcher.is_match(path))
                        }))
                        && (!classmap
                            || !exclusions.iter().any(|matcher| {
                                metadata.path.ancestors().any(|path| matcher.is_match(path))
                            }))
                    {
                        package.targets.push(file);
                    }
                }
            }
        }
        package.targets.sort_unstable();
        package.targets.dedup();
        resolution.packages.insert(id, package);
        documents.push((id, document));
    }
    for (id, document) in &documents {
        let package = &resolution.packages[*id];
        let repositories: Vec<_> = match document.get("repositories") {
            Some(Value::Array(values)) => values.iter().collect(),
            Some(Value::Object(values)) => values.values().collect(),
            _ => Vec::new(),
        };
        let matchers: Vec<_> = repositories
            .into_iter()
            .filter(|value| value.get("type").and_then(Value::as_str) == Some("path"))
            .filter_map(|value| value.get("url").and_then(Value::as_str))
            .filter(|path| !path.contains(['$', '%']) && !Path::new(path).is_absolute())
            .filter_map(|path| local::path_glob(&package.root, path))
            .collect();
        let mut dependencies = Vec::new();
        for section in ["require", "require-dev"] {
            if let Some(requirements) = document.get(section).and_then(Value::as_object) {
                for name in requirements.keys() {
                    let candidates: Vec<_> = resolution
                        .packages
                        .iter()
                        .filter(|(target, metadata)| {
                            target != id
                                && metadata.name.as_ref() == Some(name)
                                && matchers
                                    .iter()
                                    .any(|matcher| matcher.is_match(&metadata.root))
                        })
                        .map(|(target, _)| target)
                        .collect();
                    if let [target] = candidates.as_slice() {
                        dependencies.push(PackageDependency {
                            alias: name.clone(),
                            package: *target,
                        });
                    }
                }
            }
        }
        if !dependencies.is_empty() {
            let mut members = vec![*id];
            members.extend(dependencies.iter().map(|dependency| dependency.package));
            members.sort_unstable();
            members.dedup();
            resolution.workspaces.push(Workspace {
                root: package.root.clone(),
                language: "php",
                members,
            });
        }
        resolution.packages[*id].dependencies = dependencies;
    }
    Ok(resolution)
}
```

</details>
