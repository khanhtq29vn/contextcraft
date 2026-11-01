//! Literal gemspec names and Bundler local path dependencies, without evaluating Ruby.

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution, local_path};

/// Reads literal gemspec names and resolves unambiguous Bundler path dependencies.
///
/// Does not execute Ruby or resolve gems outside the repository.
///
/// # Errors
///
/// Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
/// cannot be created. Files exceeding the configured size limit are skipped.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut documents = Vec::new();

    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("ruby"))
    {
        let mut package = package.clone();

        for manifest in &package.manifests {
            let Some(source) = local::read(index, manifest, config)? else {
                continue;
            };
            let tree = local::parse(tree_sitter_ruby::LANGUAGE.into(), &source)?;

            if manifest
                .extension()
                .is_some_and(|extension| extension == "gemspec")
            {
                local::visit(tree.root_node(), |node| {
                    if node.kind() == "assignment"
                        && let Some(left) = node.child_by_field_name("left")
                        && local::text(left, source.as_bytes()).ends_with(".name")
                        && let Some(right) = node.child_by_field_name("right")
                        && let Some(name) = local::literal(right, source.as_bytes())
                    {
                        package.name = Some(name);
                    }
                });
            }

            documents.push((id, manifest.clone(), source, tree));
        }

        resolution.packages.insert(id, package);
    }

    for (id, manifest, source, tree) in documents {
        if manifest.file_name().is_none_or(|name| name != "Gemfile") {
            continue;
        }
        let base = manifest.parent().unwrap();
        local::visit(tree.root_node(), |node| {
            if node.kind() != "call" || node.child_by_field_name("receiver").is_some() {
                return;
            }
            let Some(method) = node.child_by_field_name("method") else {
                return;
            };
            let Some(arguments) = node.child_by_field_name("arguments") else {
                return;
            };
            let method = local::text(method, source.as_bytes());
            if !matches!(method, "gem" | "gemspec") {
                return;
            }
            let name = arguments
                .named_child(0)
                .and_then(|node| local::literal(node, source.as_bytes()));
            let mut directory = None;
            let mut cursor = arguments.walk();

            for argument in arguments.named_children(&mut cursor) {
                if argument.kind() != "pair" {
                    continue;
                }
                let Some(key) = argument.child_by_field_name("key") else {
                    continue;
                };
                let Some(value) = argument.child_by_field_name("value") else {
                    continue;
                };
                if local::text(key, source.as_bytes()).trim_matches(':') == "path" {
                    directory = local::literal(value, source.as_bytes());
                }
            }

            let mut grouped = false;
            if directory.is_none() {
                let mut parent = node.parent();
                while let Some(ancestor) = parent {
                    if ancestor.kind() == "call"
                        && let Some(method) = ancestor.child_by_field_name("method")
                        && local::text(method, source.as_bytes()) == "path"
                        && let Some(arguments) = ancestor.child_by_field_name("arguments")
                    {
                        directory = arguments
                            .named_child(0)
                            .and_then(|node| local::literal(node, source.as_bytes()));
                        grouped = true;
                        break;
                    }
                    parent = ancestor.parent();
                }
            }

            if method == "gemspec" && directory.is_none() {
                directory = Some(".".into());
            }
            let Some(root) = directory.and_then(|path| local_path(index, &base.join(path))) else {
                return;
            };
            let candidates: Vec<_> = resolution
                .packages
                .iter()
                .filter(|(target, package)| {
                    *target != id
                        && (package.root == root || grouped && package.root.starts_with(&root))
                        && (method == "gemspec" || package.name == name)
                })
                .map(|(id, _)| id)
                .collect();

            if let [target] = candidates.as_slice() {
                let alias = name
                    .or_else(|| resolution.packages[*target].name.clone())
                    .unwrap_or_default();
                resolution.packages[id]
                    .dependencies
                    .push(PackageDependency {
                        alias,
                        package: *target,
                    });
            }
        });
    }

    Ok(resolution)
}
