//! Static SwiftPM targets, products, and local package dependencies.

use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use tree_sitter as ts;

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{Package, PackageDependency, PackageResolution, Workspace, local_path};

struct Target {
    name: String,
    root: PathBuf,
    dependencies: Vec<(String, Option<String>)>,
    sources: Option<Vec<String>>,
    exclude: Vec<String>,
}

struct Manifest {
    name: Option<String>,
    paths: Vec<(Option<String>, PathBuf)>,
    targets: Vec<Target>,
    products: HashMap<String, Vec<String>>,
}

fn arguments<'tree>(call: ts::Node<'tree>, source: &[u8]) -> BTreeMap<String, ts::Node<'tree>> {
    let mut arguments = BTreeMap::new();
    let mut cursor = call.walk();
    for child in call.named_children(&mut cursor) {
        if child.kind() != "call_suffix" {
            continue;
        }
        let mut cursor = child.walk();
        for values in child
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "value_arguments")
        {
            let mut cursor = values.walk();
            for argument in values.named_children(&mut cursor) {
                if let (Some(name), Some(value)) = (
                    argument.child_by_field_name("name"),
                    argument.child_by_field_name("value"),
                ) {
                    arguments.insert(local::text(name, source).to_owned(), value);
                }
            }
        }
    }
    arguments
}

fn items(node: ts::Node<'_>) -> Vec<ts::Node<'_>> {
    if node.kind() != "array_literal" {
        return Vec::new();
    }
    let mut cursor = node.walk();
    node.named_children(&mut cursor).collect()
}

fn strings(node: ts::Node<'_>, source: &[u8]) -> Vec<String> {
    items(node)
        .into_iter()
        .filter_map(|node| local::literal(node, source))
        .collect()
}

fn method(node: ts::Node<'_>, source: &[u8]) -> String {
    local::text(node, source)
        .split('(')
        .next()
        .unwrap_or("")
        .trim()
        .to_owned()
}

fn read(index: &Index, path: &Path, config: &Config) -> Result<Option<Manifest>, Error> {
    let Some(source) = local::read(index, path, config)? else {
        return Ok(None);
    };
    let tree = local::parse(tree_sitter_swift::LANGUAGE.into(), &source)?;
    let bytes = source.as_bytes();
    let base = path.parent().unwrap();
    let mut manifest = None;

    local::visit(tree.root_node(), |node| {
        if node.kind() != "call_expression" || method(node, bytes) != "Package" {
            return;
        }
        let Some(declaration) = node
            .parent()
            .filter(|node| node.kind() == "property_declaration")
        else {
            return;
        };
        if declaration
            .child_by_field_name("name")
            .is_none_or(|name| local::text(name, bytes) != "package")
            || declaration
                .parent()
                .is_none_or(|parent| parent.kind() != "source_file")
        {
            return;
        }
        let args = arguments(node, bytes);
        let mut result = Manifest {
            name: args
                .get("name")
                .and_then(|node| local::literal(*node, bytes)),
            paths: Vec::new(),
            targets: Vec::new(),
            products: HashMap::new(),
        };

        if let Some(dependencies) = args.get("dependencies") {
            for dependency in items(*dependencies) {
                if method(dependency, bytes) == ".package"
                    && let Some(path) = arguments(dependency, bytes)
                        .get("path")
                        .and_then(|node| local::literal(*node, bytes))
                    && let Some(path) = local_path(index, &base.join(path))
                {
                    let alias = arguments(dependency, bytes)
                        .get("name")
                        .and_then(|node| local::literal(*node, bytes));
                    result.paths.push((alias, path));
                }
            }
        }

        if let Some(products) = args.get("products") {
            for product in items(*products) {
                let args = arguments(product, bytes);
                if let Some(name) = args
                    .get("name")
                    .and_then(|node| local::literal(*node, bytes))
                    && let Some(targets) = args.get("targets")
                {
                    result.products.insert(name, strings(*targets, bytes));
                }
            }
        }

        if let Some(targets) = args.get("targets") {
            for target in items(*targets) {
                let kind = method(target, bytes);
                if !matches!(
                    kind.as_str(),
                    ".target"
                        | ".executableTarget"
                        | ".testTarget"
                        | ".macro"
                        | ".plugin"
                        | ".systemLibrary"
                ) {
                    continue;
                }
                let args = arguments(target, bytes);
                let Some(name) = args
                    .get("name")
                    .and_then(|node| local::literal(*node, bytes))
                else {
                    continue;
                };
                if args
                    .get("path")
                    .is_some_and(|node| local::literal(*node, bytes).is_none())
                {
                    continue;
                }
                let path = args
                    .get("path")
                    .and_then(|node| local::literal(*node, bytes))
                    .unwrap_or_else(|| {
                        format!(
                            "{}/{name}",
                            if kind == ".testTarget" {
                                "Tests"
                            } else if kind == ".plugin" {
                                "Plugins"
                            } else {
                                "Sources"
                            }
                        )
                    });
                let Some(root) = local_path(index, &base.join(path)) else {
                    continue;
                };
                let mut dependencies = Vec::new();
                if let Some(values) = args.get("dependencies") {
                    for value in items(*values) {
                        if let Some(name) = local::literal(value, bytes) {
                            dependencies.push((name, None));
                        } else if matches!(
                            method(value, bytes).as_str(),
                            ".target" | ".byName" | ".product"
                        ) {
                            let args = arguments(value, bytes);
                            if let Some(name) = args
                                .get("name")
                                .and_then(|node| local::literal(*node, bytes))
                            {
                                dependencies.push((
                                    name,
                                    args.get("package")
                                        .and_then(|node| local::literal(*node, bytes)),
                                ));
                            }
                        }
                    }
                }
                result.targets.push(Target {
                    name,
                    root,
                    dependencies,
                    sources: args
                        .get("sources")
                        .filter(|node| node.kind() == "array_literal")
                        .map(|node| strings(*node, bytes)),
                    exclude: args
                        .get("exclude")
                        .map(|node| strings(*node, bytes))
                        .unwrap_or_default(),
                });
            }
        }
        manifest = Some(result);
    });
    Ok(manifest)
}

/// Discovers static SwiftPM package and target roots, plus indexed Xcode projects.
///
/// Returns packages in root-path order without executing Swift manifests.
///
/// # Errors
///
/// Returns an error if a Swift manifest cannot be read, is not UTF-8, or cannot be
/// parsed, or if targets have duplicate names or share a source directory.
/// Files exceeding the configured size limit are skipped.
pub fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "Package.swift")
    }) {
        let Some(manifest) = read(index, &file.path, config)? else {
            continue;
        };
        let root = file.path.parent().unwrap().to_path_buf();
        let mut package = local::package(root.clone(), "swift", file.path.clone());
        package.name = manifest.name;
        packages.insert(root, package);
        let mut target_roots = HashMap::new();
        let mut target_names = std::collections::HashSet::new();
        for target in manifest.targets {
            if !target_names.insert(target.name.clone()) {
                return Err(Error::Manifest {
                    path: file.path.clone(),
                    message: "duplicate Swift target name".into(),
                });
            }
            if target_roots
                .insert(target.root.clone(), target.name.clone())
                .is_some()
            {
                return Err(Error::Manifest {
                    path: file.path.clone(),
                    message:
                        "Swift targets sharing a source directory have ambiguous file ownership"
                            .into(),
                });
            }
            let package = packages.entry(target.root.clone()).or_insert_with(|| {
                let mut package = local::package(target.root, "swift", file.path.clone());
                package.manifests.clear();
                package
            });
            package.name = Some(target.name);
        }
    }
    for project in super::xcode::packages(index) {
        if let Some(package) = packages.get_mut(&project.root) {
            package.manifests.extend(project.manifests);
        } else {
            packages.insert(project.root.clone(), project);
        }
    }
    Ok(packages.into_values().collect())
}

/// Resolves indexed SwiftPM and Xcode source targets, local dependencies, and workspaces.
///
/// Package IDs refer to `index`; discover and assign packages before calling this function.
/// Swift manifests are analyzed statically, not executed.
///
/// # Errors
///
/// Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
/// cannot be created, or if an Xcode project or workspace cannot be parsed.
/// Files exceeding the configured size limit are skipped.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut documents = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "Package.swift")
    }) {
        if let Some(manifest) = read(index, &file.path, config)? {
            documents.insert(file.path.parent().unwrap().to_path_buf(), manifest);
        }
    }
    let roots: BTreeMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("swift"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    let mut resolution = PackageResolution::default();
    for &id in roots.values() {
        resolution.packages.insert(id, index.packages[id].clone());
    }

    for (root, manifest) in &documents {
        let mut members = Vec::new();
        if let Some(&id) = roots.get(root.as_path()) {
            members.push(id);
        }
        for target in &manifest.targets {
            let Some(&id) = roots.get(target.root.as_path()) else {
                continue;
            };
            members.push(id);
            let package = &mut resolution.packages[id];
            package.targets = index
                .files
                .iter()
                .filter(|(_, file)| {
                    file.language == Some("swift")
                        && file.package_id == id
                        && !file.path.ends_with("Package.swift")
                        && !target
                            .exclude
                            .iter()
                            .any(|path| file.path.starts_with(target.root.join(path)))
                        && target.sources.as_ref().is_none_or(|sources| {
                            sources
                                .iter()
                                .any(|path| file.path.starts_with(target.root.join(path)))
                        })
                })
                .map(|(id, _)| id)
                .collect();

            for (name, identity) in &target.dependencies {
                let mut targets = Vec::new();
                if identity.is_none() {
                    targets.extend(
                        manifest
                            .targets
                            .iter()
                            .filter(|target| target.name == *name)
                            .filter_map(|target| roots.get(target.root.as_path()).copied()),
                    );
                }
                if targets.is_empty() {
                    for (alias, path) in &manifest.paths {
                        let Some(dependency) = documents.get(path) else {
                            continue;
                        };
                        if identity.as_ref().is_some_and(|identity| {
                            alias.as_ref().is_none_or(|alias| alias != identity)
                                && path.file_name().is_none_or(|name| {
                                    !name.to_string_lossy().eq_ignore_ascii_case(identity)
                                })
                        }) {
                            continue;
                        }
                        if let Some(names) = dependency.products.get(name) {
                            targets.extend(
                                dependency
                                    .targets
                                    .iter()
                                    .filter(|target| names.contains(&target.name))
                                    .filter_map(|target| roots.get(target.root.as_path()).copied()),
                            );
                        }
                    }
                }
                for dependency in targets {
                    if dependency != id {
                        package.dependencies.push(PackageDependency {
                            alias: name.clone(),
                            package: dependency,
                        });
                    }
                }
            }
        }
        for (_, path) in &manifest.paths {
            if let Some(&id) = roots.get(path.as_path()) {
                members.push(id);
            }
        }
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.clone(),
            language: "swift",
            members,
        });
    }
    super::xcode::discover(index, config, &mut resolution)?;
    Ok(resolution)
}
