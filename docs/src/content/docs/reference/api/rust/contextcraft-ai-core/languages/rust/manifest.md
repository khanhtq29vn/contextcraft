---
title: "contextcraft-ai-core::languages::rust::manifest"
description: "Discover local package metadata and workspace relationships."
editUrl: false
sidebar:
  order: 58
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Discover local package metadata and workspace relationships.

## Structs

### <span id="struct.RustPackage"></span><code style="font-size: 0.85em">struct RustPackage</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Cargo package metadata needed for local module and import resolution.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `name` | `String` | Declared Cargo package name. |
| `crate_name` | `String` | Library crate name with hyphens normalized to underscores. |
| `edition` | `String` | Effective Rust edition, including workspace inheritance. |
| `library` | `Option<FileId>` | Indexed library entry file, if available. |
| `targets` | `Vec<Target>` | Indexed build targets, including tests, examples, and build scripts. |
| `dependencies` | `Vec<LocalDependency>` | Local path dependencies across dependency kinds and target configurations. |

### <span id="struct.Target"></span><code style="font-size: 0.85em">struct Target</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

An indexed Cargo target entry point and its build category.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `FileId` | Entry file ID in the associated index. |
| `kind` | `TargetKind` | Build category used for dependency visibility. |

### <span id="struct.LocalDependency"></span><code style="font-size: 0.85em">struct LocalDependency</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Resolved Cargo path dependency, retaining its visibility category.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `alias` | `String` | Crate name used in imports, with hyphens normalized to underscores. |
| `package` | `PackageId` | Indexed local dependency package. |
| `kind` | `DependencyKind` | Dependency table category controlling target visibility. |
| `target` | `Option<String>` | Target selector from a target-specific table, if present.<br>Retained as metadata rather than evaluated for the current host. |

## Enums

### <span id="enum.TargetKind"></span><code style="font-size: 0.85em">enum TargetKind</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Cargo target category controlling dependency visibility.

#### Variants

- **`Library`** - Library entry point.
- **`Binary`** - Executable entry point.
- **`Build`** - Package build script.
- **`Example`** - Example program.
- **`Test`** - Integration test target.
- **`Bench`** - Benchmark target.

### <span id="enum.DependencyKind"></span><code style="font-size: 0.85em">enum DependencyKind</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

Cargo dependency table category.

#### Variants

- **`Normal`** - Dependency from a `dependencies` table.
- **`Dev`** - Dependency from a `dev-dependencies` table.
- **`Build`** - Dependency from a `build-dependencies` table.

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<(ArenaMap<PackageId, RustPackage>, Vec<Workspace>), Error>
```

Discovers Cargo targets, workspaces, and local path dependencies.

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
) -> Result<(ArenaMap<PackageId, RustPackage>, Vec<Workspace>), Error> {
    let mut documents = BTreeMap::new();

    for (id, package) in index.packages.iter() {
        if package.language != Some("rust") {
            continue;
        }

        let Some(manifest) = package.manifests.first() else {
            continue;
        };

        let Some(value) = read_toml(index, manifest, config)? else {
            continue;
        };

        documents.insert(
            id,
            Document {
                root: package.root.clone(),
                value,
            },
        );
    }

    let roots: HashMap<_, _> = documents
        .iter()
        .map(|(&id, doc)| (doc.root.as_path(), id))
        .collect();

    let (workspaces, owners) = discover_workspaces(index, &documents, &roots)?;

    let files: HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();

    let mut packages = ArenaMap::new();

    for (&id, doc) in &documents {
        let Some(package) = doc.value.get("package") else {
            continue;
        };

        let Some(name) = package.get("name").and_then(Value::as_str) else {
            return Err(Error::Manifest {
                path: doc.root.join("Cargo.toml"),
                message: "missing package.name".into(),
            });
        };

        let edition = package
            .get("edition")
            .and_then(Value::as_str)
            .or_else(|| {
                package
                    .get("edition")?
                    .get("workspace")?
                    .as_bool()
                    .filter(|&v| v)?;

                documents
                    .get(owners.get(&id)?)?
                    .value
                    .get("workspace")?
                    .get("package")?
                    .get("edition")?
                    .as_str()
            })
            .unwrap_or("2015")
            .to_owned();
        let targets = targets(index, doc, name, &files);
        let library = targets
            .iter()
            .find(|target| target.kind == TargetKind::Library)
            .map(|target| target.root);
        let crate_name = doc
            .value
            .get("lib")
            .and_then(|lib| lib.get("name"))
            .and_then(Value::as_str)
            .unwrap_or(name)
            .replace('-', "_");
        let mut dependencies = Vec::new();

        for (alias, kind, target, dependency) in dependency_tables(&doc.value) {
            let (dependency, base) = inherited_dependency(
                alias,
                dependency,
                doc,
                owners.get(&id).and_then(|id| documents.get(id)),
            );
            let Some(path) = dependency.get("path").and_then(Value::as_str) else {
                continue;
            };

            let Some(root) = local_path(index, &base.join(path)) else {
                continue;
            };

            let Some(&target_package) = roots.get(root.as_path()) else {
                continue;
            };

            let expected_name = dependency
                .get("package")
                .and_then(Value::as_str)
                .unwrap_or(alias);

            if documents[&target_package]
                .value
                .get("package")
                .and_then(|p| p.get("name"))
                .and_then(Value::as_str)
                != Some(expected_name)
            {
                continue;
            }

            let crate_alias = if dependency.get("package").is_some() {
                alias
            } else {
                documents[&target_package]
                    .value
                    .get("lib")
                    .and_then(|lib| lib.get("name"))
                    .and_then(Value::as_str)
                    .unwrap_or(alias)
            };

            dependencies.push(LocalDependency {
                alias: crate_alias.replace('-', "_"),
                package: target_package,
                kind,
                target: target.map(str::to_owned),
            });
        }

        packages.insert(
            id,
            RustPackage {
                name: name.to_owned(),
                crate_name,
                edition,
                library,
                targets,
                dependencies,
            },
        );
    }

    Ok((packages, workspaces))
}
```

</details>
