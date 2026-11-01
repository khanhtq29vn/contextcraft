//! Static Maven coordinates, reactor membership, and local declared dependencies.
//!
//! Project-local properties are substituted without executing Maven. Profiles, plugins,
//! imported BOMs, and properties or dependencies inherited from parent POMs are not evaluated.

use std::collections::HashMap;
use std::path::PathBuf;

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution, Workspace, local_path};

fn child<'a, 'input>(
    node: roxmltree::Node<'a, 'input>,
    name: &str,
) -> Option<roxmltree::Node<'a, 'input>> {
    node.children()
        .find(|child| child.is_element() && child.tag_name().name() == name)
}

fn value(node: roxmltree::Node<'_, '_>, name: &str) -> Option<String> {
    child(node, name)?
        .text()
        .map(|text| text.trim().to_owned())
        .filter(|text| !text.is_empty())
}

fn expand(value: &str, properties: &HashMap<String, String>) -> Option<String> {
    let mut value = value.to_owned();
    for _ in 0..16 {
        let Some(start) = value.find("${") else {
            return Some(value);
        };
        let end = start + value[start..].find('}')?;
        let replacement = properties.get(&value[start + 2..end])?;
        value.replace_range(start..=end, replacement);
    }
    None
}

struct Pom {
    group: String,
    artifact: String,
    version: Option<String>,
    dependencies: Vec<(String, Option<String>)>,
    modules: Vec<PathBuf>,
}

/// Resolves Maven reactor membership and unambiguous local dependency coordinates.
///
/// # Errors
///
/// Returns an error for unreadable, invalid UTF-8, or malformed XML manifests.
/// Oversized manifests and computed values that cannot be resolved are skipped.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut documents = Vec::new();
    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("jvm"))
    {
        let Some(manifest) = package
            .manifests
            .iter()
            .find(|path| path.file_name().is_some_and(|name| name == "pom.xml"))
        else {
            continue;
        };
        let Some(source) = local::read(index, manifest, config)? else {
            continue;
        };
        let document = roxmltree::Document::parse(&source).map_err(|error| Error::Manifest {
            path: manifest.clone(),
            message: error.to_string(),
        })?;
        let root = document.root_element();
        if root.tag_name().name() != "project" {
            continue;
        }
        let mut properties = HashMap::new();
        if let Some(values) = child(root, "properties") {
            for property in values.children().filter(|node| node.is_element()) {
                if let Some(value) = property.text() {
                    properties.insert(property.tag_name().name().into(), value.trim().into());
                }
            }
        }
        let parent = child(root, "parent");
        for name in ["groupId", "artifactId", "version"] {
            if let Some(value) = value(root, name).or_else(|| {
                if name != "artifactId" {
                    parent.and_then(|parent| value(parent, name))
                } else {
                    None
                }
            }) {
                properties.insert(format!("project.{name}"), value.clone());
                properties.insert(format!("pom.{name}"), value);
            }
            if let Some(value) = parent.and_then(|parent| value(parent, name)) {
                properties.insert(format!("project.parent.{name}"), value);
            }
        }
        let Some(group) = properties
            .get("project.groupId")
            .and_then(|value| expand(value, &properties))
        else {
            continue;
        };
        let Some(artifact) = properties
            .get("project.artifactId")
            .and_then(|value| expand(value, &properties))
        else {
            continue;
        };
        let version = properties
            .get("project.version")
            .and_then(|value| expand(value, &properties));
        let mut dependencies = Vec::new();
        if let Some(declarations) = child(root, "dependencies") {
            for declaration in declarations
                .children()
                .filter(|node| node.is_element() && node.tag_name().name() == "dependency")
            {
                if let (Some(group), Some(artifact)) = (
                    value(declaration, "groupId").and_then(|value| expand(&value, &properties)),
                    value(declaration, "artifactId").and_then(|value| expand(&value, &properties)),
                ) {
                    let raw_version = value(declaration, "version");
                    let version = raw_version
                        .as_deref()
                        .and_then(|value| expand(value, &properties));
                    if raw_version.is_some() && version.is_none() {
                        continue;
                    }
                    dependencies.push((format!("{group}:{artifact}"), version));
                }
            }
        }
        let modules = child(root, "modules")
            .into_iter()
            .flat_map(|modules| modules.children())
            .filter(|node| node.is_element() && node.tag_name().name() == "module")
            .filter_map(|node| {
                node.text()
                    .and_then(|value| expand(value.trim(), &properties))
            })
            .filter_map(|path| local_path(index, &package.root.join(path)))
            .collect();
        documents.push((
            id,
            Pom {
                group,
                artifact,
                version,
                dependencies,
                modules,
            },
        ));
    }
    for (id, pom) in &documents {
        let mut package = index.packages[*id].clone();
        package.name = Some(format!("{}:{}", pom.group, pom.artifact));
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| {
                file.package_id == *id && matches!(file.language, Some("java" | "kotlin"))
            })
            .map(|(file, _)| file)
            .collect();
        for (name, version) in &pom.dependencies {
            let candidates: Vec<_> = documents
                .iter()
                .filter(|(target, other)| {
                    target != id
                        && format!("{}:{}", other.group, other.artifact) == *name
                        && version
                            .as_ref()
                            .is_none_or(|version| other.version.as_ref() == Some(version))
                })
                .map(|(id, _)| *id)
                .collect();
            if let [target] = candidates.as_slice() {
                package.dependencies.push(PackageDependency {
                    alias: name.clone(),
                    package: *target,
                });
            }
        }
        if !pom.modules.is_empty() {
            let mut members = vec![*id];
            for root in &pom.modules {
                members.extend(
                    documents
                        .iter()
                        .filter(|(id, _)| index.packages[*id].root == *root)
                        .map(|(id, _)| *id),
                );
            }
            members.sort_unstable();
            members.dedup();
            resolution.workspaces.push(Workspace {
                root: package.root.clone(),
                language: "jvm",
                members,
            });
        }
        resolution.packages.insert(*id, package);
    }
    Ok(resolution)
}
