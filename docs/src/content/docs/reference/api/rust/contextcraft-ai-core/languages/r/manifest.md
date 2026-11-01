---
title: "contextcraft-ai-core::languages::r::manifest"
description: "R DESCRIPTION fields and named dependencies between indexed local packages."
editUrl: false
sidebar:
  order: 61
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

R DESCRIPTION fields and named dependencies between indexed local packages.

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Reads DESCRIPTION names and links unambiguous declared local package dependencies.

**Errors:**

Returns an error for unreadable, invalid UTF-8, or malformed DESCRIPTION files.
Oversized files and dependencies outside the indexed repository are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut requirements = Vec::new();
    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("r"))
    {
        let Some(manifest) = package.manifests.first() else {
            continue;
        };
        let Some(source) = local::read(index, manifest, config)? else {
            continue;
        };
        let fields = fields(&source).ok_or_else(|| Error::Manifest {
            path: manifest.clone(),
            message: "invalid DESCRIPTION fields".into(),
        })?;
        let mut package = package.clone();
        package.name = fields.get("Package").cloned();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| {
                file.package_id == id
                    && file.language == Some("r")
                    && file.path.starts_with(package.root.join("R"))
            })
            .map(|(file, _)| file)
            .collect();
        let mut dependencies = Vec::new();
        for field in ["Depends", "Imports", "LinkingTo", "Suggests", "Enhances"] {
            if let Some(value) = fields.get(field) {
                dependencies.extend(names(value).map(str::to_owned));
            }
        }
        requirements.push((id, dependencies));
        resolution.packages.insert(id, package);
    }
    for (id, names) in requirements {
        for name in names {
            let candidates: Vec<_> = resolution
                .packages
                .iter()
                .filter(|(target, metadata)| *target != id && metadata.name.as_ref() == Some(&name))
                .map(|(target, _)| target)
                .collect();
            if let [target] = candidates.as_slice() {
                resolution.packages[id]
                    .dependencies
                    .push(PackageDependency {
                        alias: name,
                        package: *target,
                    });
            }
        }
    }
    Ok(resolution)
}
```

</details>
