---
title: "contextcraft-ai-core::languages::csharp::manifest"
description: ".NET project references and solution membership, without evaluating MSBuild."
editUrl: false
sidebar:
  order: 21
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

.NET project references and solution membership, without evaluating MSBuild.

## Functions

### <span id="fn.discover"></span><code style="font-size: 0.85em">fn discover</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn discover(
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Resolves indexed .NET projects, source membership, and solution workspaces.

Reads literal project references without evaluating MSBuild properties or conditions.

**Errors:**

Returns an error if a project or solution cannot be read, is not UTF-8, or
contains invalid XML. Files exceeding the configured size limit are skipped.

<details>
<summary>Source</summary>

```rust
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let projects: HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("csharp"))
        .flat_map(|(id, package)| package.manifests.iter().map(move |path| (path.clone(), id)))
        .collect();
    let mut resolution = PackageResolution::default();

    for (manifest, &id) in &projects {
        let Some(source) = local::read(index, manifest, config)? else {
            continue;
        };
        let document = xml(manifest, &source)?;
        let mut package = index.packages[id].clone();
        package.name = document
            .descendants()
            .find(|node| node.has_tag_name("AssemblyName") && node.attribute("Condition").is_none())
            .and_then(|node| node.text())
            .filter(|name| !name.contains("$("))
            .map(|name| name.trim().to_owned())
            .or_else(|| {
                manifest
                    .file_stem()
                    .map(|name| name.to_string_lossy().into_owned())
            });
        package.targets = compile_files(index, id, manifest, &document);

        for node in document
            .descendants()
            .filter(|node| node.has_tag_name("ProjectReference"))
        {
            if node
                .attribute("ReferenceOutputAssembly")
                .is_some_and(|value| value.eq_ignore_ascii_case("false"))
                || node.children().any(|child| {
                    child.has_tag_name("ReferenceOutputAssembly")
                        && child
                            .text()
                            .is_some_and(|value| value.trim().eq_ignore_ascii_case("false"))
                })
            {
                continue;
            }
            let Some(path) = node.attribute("Include") else {
                continue;
            };
            if path.contains(['$', '*', '?', '%']) {
                continue;
            }
            let path = manifest.parent().unwrap().join(path.replace('\\', "/"));
            if let Some(path) = local_path(index, &path)
                && let Some(&target) = projects.get(&path)
                && target != id
            {
                package.dependencies.push(PackageDependency {
                    alias: index.packages[target].manifests[0]
                        .file_stem()
                        .unwrap()
                        .to_string_lossy()
                        .into_owned(),
                    package: target,
                });
            }
        }
        resolution.packages.insert(id, package);
    }

    let solution_project =
        regex::Regex::new(r#"^Project\("[^"]*"\)\s*=\s*"[^"]*",\s*"([^"]+)""#).unwrap();

    for (_, file) in index.files.iter() {
        let extension = file
            .path
            .extension()
            .and_then(|extension| extension.to_str());
        if !matches!(extension, Some("sln" | "slnx")) {
            continue;
        }
        let Some(source) = local::read(index, &file.path, config)? else {
            continue;
        };
        let root = file.path.parent().unwrap();
        let mut paths = Vec::new();

        if extension == Some("slnx") {
            let document = xml(&file.path, &source)?;
            paths.extend(
                document
                    .descendants()
                    .filter(|node| node.has_tag_name("Project"))
                    .filter_map(|node| node.attribute("Path"))
                    .map(str::to_owned),
            );
        } else {
            for line in source
                .lines()
                .map(str::trim)
                .filter(|line| line.starts_with("Project("))
            {
                if let Some(captures) = solution_project.captures(line) {
                    paths.push(captures[1].to_owned());
                }
            }
        }

        let mut members: Vec<_> = paths
            .iter()
            .filter_map(|path| local_path(index, &root.join(path.replace('\\', "/"))))
            .filter_map(|path| projects.get(&path).copied())
            .collect();
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.to_path_buf(),
            language: "csharp",
            members,
        });
    }

    Ok(resolution)
}
```

</details>
