//! Literal Mix application names, path dependencies, and umbrella membership.

use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

use tree_sitter as ts;

use crate::Config;
use crate::error::Error;
use crate::index::{Index, PackageId};
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution, Workspace, local_path};

struct Manifest {
    app: Option<String>,
    apps_path: Option<PathBuf>,
    apps: Option<HashSet<String>>,
    dependencies: Vec<(String, Option<PathBuf>)>,
}

fn child<'tree>(node: ts::Node<'tree>, kind: &str) -> Option<ts::Node<'tree>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .find(|node| node.kind() == kind)
}

fn target<'a>(node: ts::Node<'_>, source: &'a [u8]) -> &'a str {
    node.child_by_field_name("target")
        .filter(|node| node.kind() == "identifier")
        .map_or("", |node| local::text(node, source))
}

fn atom(node: ts::Node<'_>, source: &[u8]) -> Option<String> {
    (node.kind() == "atom")
        .then(|| {
            local::text(node, source)
                .strip_prefix(':')
                .map(str::to_owned)
        })
        .flatten()
}

fn literal(node: ts::Node<'_>, source: &[u8]) -> Option<String> {
    if local::text(node, source).starts_with("\"\"\"") {
        return None;
    }
    local::literal(node, source)
}

fn keywords<'tree>(node: ts::Node<'tree>, source: &[u8]) -> HashMap<String, ts::Node<'tree>> {
    let Some(keywords) = child(node, "keywords") else {
        return HashMap::new();
    };
    let mut cursor = keywords.walk();
    let mut values = HashMap::new();
    for pair in keywords.named_children(&mut cursor) {
        if let (Some(key), Some(value)) = (
            pair.child_by_field_name("key"),
            pair.child_by_field_name("value"),
        ) && let Some(key) = local::text(key, source).trim().strip_suffix(':')
        {
            // Elixir keyword lookup uses the first value when keys are repeated.
            values.entry(key.to_owned()).or_insert(value);
        }
    }
    values
}

fn value<'tree>(node: ts::Node<'tree>, source: &[u8]) -> Option<ts::Node<'tree>> {
    if let Some(body) = child(node, "do_block") {
        let mut cursor = body.walk();
        let mut expressions = body
            .named_children(&mut cursor)
            .filter(|node| node.kind() != "comment");
        let value = expressions.next()?;
        return expressions.next().is_none().then_some(value);
    }
    keywords(child(node, "arguments")?, source)
        .get("do")
        .copied()
}

fn expand<'tree>(
    mut node: ts::Node<'tree>,
    functions: &HashMap<String, Option<ts::Node<'tree>>>,
    source: &[u8],
) -> Option<ts::Node<'tree>> {
    let mut seen = HashSet::new();
    while node.kind() == "call" || node.kind() == "identifier" {
        let name = if node.kind() == "identifier" {
            local::text(node, source)
        } else {
            let name = target(node, source);
            if child(node, "arguments").is_some_and(|args| args.named_child_count() != 0) {
                return None;
            }
            name
        };
        if !seen.insert(name) {
            return None;
        }
        node = *functions.get(name)?.as_ref()?;
    }
    Some(node)
}

fn read(
    index: &Index,
    manifest: &std::path::Path,
    config: &Config,
) -> Result<Option<Manifest>, Error> {
    let Some(source) = local::read(index, manifest, config)? else {
        return Ok(None);
    };
    let tree = local::parse(tree_sitter_elixir::LANGUAGE.into(), &source)?;
    if tree.root_node().has_error() {
        return Ok(None);
    }
    let bytes = source.as_bytes();
    let mut projects = Vec::new();
    let mut cursor = tree.root_node().walk();
    for module in tree.root_node().named_children(&mut cursor) {
        if target(module, bytes) != "defmodule" {
            continue;
        }
        let Some(body) = child(module, "do_block") else {
            continue;
        };
        let mut cursor = body.walk();
        if body.named_children(&mut cursor).any(|node| {
            target(node, bytes) == "use"
                && child(node, "arguments")
                    .is_some_and(|args| local::text(args, bytes).trim() == "Mix.Project")
        }) {
            projects.push(body);
        }
    }
    let [body] = projects.as_slice() else {
        return Ok(None);
    };
    let mut functions = HashMap::new();
    let mut cursor = body.walk();
    for function in body.named_children(&mut cursor) {
        if !matches!(target(function, bytes), "def" | "defp") {
            continue;
        }
        let Some(signature) = child(function, "arguments").and_then(|args| args.named_child(0))
        else {
            continue;
        };
        let name = if signature.kind() == "identifier" {
            local::text(signature, bytes)
        } else {
            if child(signature, "arguments").is_some_and(|args| args.named_child_count() != 0) {
                continue;
            }
            target(signature, bytes)
        };
        if name.is_empty() {
            continue;
        }
        functions
            .entry(name.to_owned())
            .and_modify(|value| *value = None)
            .or_insert_with(|| value(function, bytes));
    }
    let Some(project) = functions
        .get("project")
        .copied()
        .flatten()
        .and_then(|node| expand(node, &functions, bytes))
        .filter(|node| node.kind() == "list")
    else {
        return Ok(None);
    };
    let fields = keywords(project, bytes);
    let root = manifest.parent().unwrap();
    let mut result = Manifest {
        app: fields.get("app").and_then(|&node| atom(node, bytes)),
        apps_path: fields
            .get("apps_path")
            .and_then(|&node| literal(node, bytes))
            .and_then(|path| local_path(index, &root.join(path))),
        apps: None,
        dependencies: Vec::new(),
    };
    if let Some(&apps) = fields.get("apps") {
        let mut cursor = apps.walk();
        result.apps = (apps.kind() == "list")
            .then(|| {
                apps.named_children(&mut cursor)
                    .filter(|node| node.kind() != "comment")
                    .map(|node| atom(node, bytes))
                    .collect::<Option<HashSet<_>>>()
            })
            .flatten();
        if result.apps.is_none() {
            result.apps_path = None;
        }
    }
    if let Some(dependencies) = fields
        .get("deps")
        .and_then(|&node| expand(node, &functions, bytes))
        .filter(|node| node.kind() == "list")
    {
        let mut cursor = dependencies.walk();
        for dependency in dependencies
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "tuple")
        {
            let Some(name) = dependency.named_child(0).and_then(|node| atom(node, bytes)) else {
                continue;
            };
            let options = keywords(dependency, bytes);
            if options.contains_key("git")
                || options.contains_key("github")
                || options.contains_key("hex")
            {
                continue;
            }
            if let Some(&path) = options.get("path") {
                if let Some(path) =
                    literal(path, bytes).and_then(|path| local_path(index, &root.join(path)))
                {
                    result.dependencies.push((name, Some(path)));
                }
            } else if options
                .get("in_umbrella")
                .is_some_and(|&node| node.kind() == "boolean" && local::text(node, bytes) == "true")
            {
                result.dependencies.push((name, None));
            }
        }
    }
    Ok(Some(result))
}

/// Resolves literal Mix path dependencies and umbrella application membership.
///
/// Only simple zero-argument helpers returning literal lists are followed. Mix
/// code is never executed; remote dependencies and dynamic expressions are ignored.
///
/// # Errors
///
/// Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
/// cannot be created. Oversized and syntactically malformed manifests are skipped.
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
