//! Literal sbt project roots, dependsOn relationships, and build membership.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{Package, PackageDependency, PackageResolution, Workspace, local_path};

struct Project {
    name: String,
    root: PathBuf,
    dependencies: Vec<String>,
}

fn projects(index: &Index, manifest: &Path, config: &Config) -> Result<Vec<Project>, Error> {
    let Some(source) = local::read(index, manifest, config)? else {
        return Ok(Vec::new());
    };
    let tree = local::parse(tree_sitter_scala::LANGUAGE.into(), &source)?;
    let mut projects = Vec::new();
    let mut cursor = tree.root_node().walk();

    for node in tree.root_node().named_children(&mut cursor) {
        if node.kind() != "val_definition" {
            continue;
        }
        let Some(pattern) = node.child_by_field_name("pattern") else {
            continue;
        };
        if pattern.kind() != "identifier" {
            continue;
        }
        let Some(value) = node.child_by_field_name("value") else {
            continue;
        };
        let name = local::text(pattern, source.as_bytes()).to_owned();
        let mut is_project = false;
        let mut directory = None;
        let mut explicit_directory = false;
        let mut dependencies = Vec::new();

        local::visit(value, |node| {
            if node.kind() == "identifier" && local::text(node, source.as_bytes()) == "project" {
                is_project = true;
            }
            if node.kind() == "infix_expression"
                && let Some(operator) = node.child_by_field_name("operator")
                && local::text(operator, source.as_bytes()) == "in"
                && let Some(right) = node.child_by_field_name("right")
            {
                explicit_directory = true;
                local::visit(right, |node| {
                    if node.kind() == "call_expression"
                        && let Some(function) = node.child_by_field_name("function")
                        && local::text(function, source.as_bytes()) == "file"
                        && let Some(arguments) = node.child_by_field_name("arguments")
                    {
                        directory = arguments
                            .named_child(0)
                            .and_then(|node| local::literal(node, source.as_bytes()));
                    }
                });
            }
            if node.kind() != "call_expression" {
                return;
            }
            let Some(function) = node.child_by_field_name("function") else {
                return;
            };
            let Some(arguments) = node.child_by_field_name("arguments") else {
                return;
            };
            if local::text(function, source.as_bytes()) == "Project" {
                is_project = true;
                explicit_directory = true;
                if let Some(directory_call) = arguments.named_child(1) {
                    local::visit(directory_call, |node| {
                        if node.kind() == "call_expression"
                            && let Some(function) = node.child_by_field_name("function")
                            && local::text(function, source.as_bytes()) == "file"
                            && let Some(arguments) = node.child_by_field_name("arguments")
                        {
                            directory = arguments
                                .named_child(0)
                                .and_then(|node| local::literal(node, source.as_bytes()));
                        }
                    });
                }
            }
            let method = function
                .child_by_field_name("field")
                .map(|field| local::text(field, source.as_bytes()))
                .unwrap_or("");

            if method == "in" {
                explicit_directory = true;
                local::visit(arguments, |node| {
                    if node.kind() == "call_expression"
                        && let Some(function) = node.child_by_field_name("function")
                        && local::text(function, source.as_bytes()) == "file"
                        && let Some(arguments) = node.child_by_field_name("arguments")
                    {
                        directory = arguments
                            .named_child(0)
                            .and_then(|node| local::literal(node, source.as_bytes()));
                    }
                });
            }
            if method == "dependsOn" {
                let mut cursor = arguments.walk();
                for argument in arguments.named_children(&mut cursor) {
                    let argument = if argument.kind() == "infix_expression" {
                        argument.child_by_field_name("left").unwrap_or(argument)
                    } else {
                        argument
                    };
                    if argument.kind() == "identifier" {
                        dependencies.push(local::text(argument, source.as_bytes()).into());
                    }
                }
            }
        });

        if is_project && !(explicit_directory && directory.is_none()) {
            let root = manifest
                .parent()
                .unwrap()
                .join(directory.as_deref().unwrap_or(&name));
            if let Some(root) = local_path(index, &root) {
                projects.push(Project {
                    name,
                    root,
                    dependencies,
                });
            }
        }
    }

    Ok(projects)
}

/// Discovers sbt build roots and literal subproject directories in root-path order.
///
/// Does not evaluate sbt. Project directories must resolve within the repository.
///
/// # Errors
///
/// Returns an error if a build file cannot be read, is not UTF-8, or its syntax tree
/// cannot be created. Files exceeding the configured size limit are skipped.
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

/// Resolves indexed Scala source targets, literal `dependsOn` links, and sbt workspaces.
///
/// Package IDs refer to `index`; discover and assign packages before calling this function.
///
/// # Errors
///
/// Returns an error if a build file cannot be read, is not UTF-8, or its syntax tree
/// cannot be created. Files exceeding the configured size limit are skipped.
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
