---
title: "contextcraft-ai-core::languages::python::manifest"
description: "Discover local package metadata and workspace relationships."
editUrl: false
sidebar:
  order: 51
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Discover local package metadata and workspace relationships.

## Structs

### <span id="struct.PythonPackage"></span><code style="font-size: 0.85em">struct PythonPackage</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Source roots used to resolve modules owned by a Python package.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `roots` | `Vec<SourceRoot>` | Configured or inferred import roots, in discovery order. |

### <span id="struct.SourceRoot"></span><code style="font-size: 0.85em">struct SourceRoot</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Maps a repository directory to an importable module prefix.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `path` | `PathBuf` | Source directory relative to the repository root. |
| `prefix` | `Vec<String>` | Module prefix mounted at this directory. Empty for an ordinary import root. |

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<(PackageResolution, ArenaMap<PackageId, PythonPackage>), Error>
```

Discovers Python source roots, uv workspaces, and explicit local dependencies.

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
) -> Result<(PackageResolution, ArenaMap<PackageId, PythonPackage>), Error> {
    let mut documents = BTreeMap::new();
    let mut resolution = PackageResolution::default();

    for (id, package) in index.packages.iter() {
        if package.language != Some("python") {
            continue;
        }

        let Some(manifest) = package.manifests.iter().find(|path| {
            path.file_name()
                .is_some_and(|name| name == "pyproject.toml")
        }) else {
            continue;
        };

        let Some(value) = read_toml(index, manifest, config)? else {
            continue;
        };

        let mut package = package.clone();
        package.name = value
            .get("project")
            .and_then(|project| project.get("name"))
            .and_then(Value::as_str)
            .map(str::to_owned);

        resolution.packages.insert(id, package);
        documents.insert(id, value);
    }

    let (workspaces, owners) = discover_workspaces(index, &documents, &resolution.packages)?;
    resolution.workspaces = workspaces;

    link_dependencies(index, &documents, &owners, &mut resolution)?;

    let mut packages = ArenaMap::new();

    for (id, package) in index.packages.iter() {
        if package.language == Some("python")
            || package.language.is_none()
                && index
                    .files
                    .iter()
                    .any(|(_, file)| file.package_id == id && file.language == Some("python"))
        {
            packages.insert(
                id,
                PythonPackage {
                    roots: source_roots(index, id, documents.get(&id)),
                },
            );
        }
    }

    Ok((resolution, packages))
}
```

</details>
