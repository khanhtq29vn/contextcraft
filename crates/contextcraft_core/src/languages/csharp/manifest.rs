//! .NET project references and solution membership, without evaluating MSBuild.

use std::collections::{HashMap, HashSet};
use std::path::{Component, Path, PathBuf};

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution, Workspace, local_path};

fn xml<'a>(path: &Path, source: &'a str) -> Result<roxmltree::Document<'a>, Error> {
    roxmltree::Document::parse(source).map_err(|error| Error::Manifest {
        path: path.to_path_buf(),
        message: error.to_string(),
    })
}

/// Resolves indexed .NET projects, source membership, and solution workspaces.
///
/// Reads literal project references without evaluating MSBuild properties or conditions.
///
/// # Errors
///
/// Returns an error if a project or solution cannot be read, is not UTF-8, or
/// contains invalid XML. Files exceeding the configured size limit are skipped.
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

fn pattern(root: &Path, value: &str) -> Option<globset::GlobMatcher> {
    if value.contains(['$', '%']) {
        return None;
    }
    let mut path = PathBuf::new();
    for component in root.join(value.replace('\\', "/")).components() {
        match component {
            Component::Normal(value) => path.push(value),
            Component::CurDir => {}
            Component::ParentDir => {
                if !path.pop() {
                    return None;
                }
            }
            _ => return None,
        }
    }
    globset::GlobBuilder::new(&path.to_string_lossy())
        .literal_separator(true)
        .build()
        .ok()
        .map(|glob| glob.compile_matcher())
}

fn compile_files(
    index: &Index,
    package: PackageId,
    manifest: &Path,
    document: &roxmltree::Document<'_>,
) -> Vec<FileId> {
    let root = manifest.parent().unwrap();
    let sdk = document.root_element().attribute("Sdk").is_some()
        || document.descendants().any(|node| node.has_tag_name("Sdk"));
    let disabled = document.descendants().any(|node| {
        (node.has_tag_name("EnableDefaultCompileItems") || node.has_tag_name("EnableDefaultItems"))
            && node
                .ancestors()
                .all(|node| node.attribute("Condition").is_none())
            && node
                .text()
                .is_some_and(|text| text.trim().eq_ignore_ascii_case("false"))
    });
    let mut files: HashSet<_> = index
        .files
        .iter()
        .filter(|(_, file)| {
            sdk && !disabled && file.package_id == package && file.language == Some("csharp")
        })
        .map(|(id, _)| id)
        .collect();

    for node in document
        .descendants()
        .filter(|node| node.has_tag_name("Compile"))
    {
        if let Some(include) = node.attribute("Include") {
            let includes: Vec<_> = include
                .split(';')
                .filter_map(|value| pattern(root, value.trim()))
                .collect();
            let excludes: Vec<_> = node
                .attribute("Exclude")
                .unwrap_or("")
                .split(';')
                .filter_map(|value| pattern(root, value.trim()))
                .collect();
            for (id, file) in index
                .files
                .iter()
                .filter(|(_, file)| file.language == Some("csharp"))
            {
                if includes.iter().any(|pattern| pattern.is_match(&file.path))
                    && !excludes.iter().any(|pattern| pattern.is_match(&file.path))
                {
                    files.insert(id);
                }
            }
        }
        if let Some(remove) = node.attribute("Remove")
            && node
                .ancestors()
                .all(|node| node.attribute("Condition").is_none())
        {
            let patterns: Vec<_> = remove
                .split(';')
                .filter_map(|value| pattern(root, value.trim()))
                .collect();
            files.retain(|&id| {
                !patterns
                    .iter()
                    .any(|pattern| pattern.is_match(&index.files[id].path))
            });
        }
    }
    let mut files: Vec<_> = files.into_iter().collect();
    files.sort_unstable();
    files
}
