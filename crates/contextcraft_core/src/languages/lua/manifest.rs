//! Static LuaRocks package names and declared local rock dependencies.

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution};

/// Reads literal LuaRocks package names and links unambiguous local dependencies.
///
/// Does not execute rockspecs or resolve external packages.
///
/// # Errors
///
/// Returns an error if a manifest cannot be read, is not UTF-8, or its syntax tree
/// cannot be created. Files exceeding the configured size limit are skipped.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut dependencies = Vec::new();

    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("lua"))
    {
        let mut package = package.clone();
        let mut required = Vec::new();

        for manifest in &package.manifests {
            let Some(source) = local::read(index, manifest, config)? else {
                continue;
            };
            let tree = local::parse(tree_sitter_lua::LANGUAGE.into(), &source)?;
            let root = tree.root_node();
            let mut cursor = root.walk();

            for node in root.named_children(&mut cursor) {
                if node.kind() != "assignment_statement" {
                    continue;
                }
                let mut cursor = node.walk();
                let children: Vec<_> = node.named_children(&mut cursor).collect();
                let [variables, expressions] = children.as_slice() else {
                    continue;
                };
                let Some(name) = variables.named_child(0) else {
                    continue;
                };
                let Some(value) = expressions.named_child(0) else {
                    continue;
                };

                match local::text(name, source.as_bytes()) {
                    "package" => package.name = local::literal(value, source.as_bytes()),
                    "dependencies" if value.kind() == "table_constructor" => {
                        let mut cursor = value.walk();
                        for field in value.named_children(&mut cursor) {
                            if field.child_by_field_name("name").is_some() {
                                continue;
                            }
                            if let Some(value) = field.child_by_field_name("value")
                                && let Some(value) = local::literal(value, source.as_bytes())
                                && let Some(name) = value.split_whitespace().next()
                            {
                                required.push(name.to_owned());
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        dependencies.push((id, required));
        resolution.packages.insert(id, package);
    }

    for (id, names) in dependencies {
        for name in names {
            let matches: Vec<_> = resolution
                .packages
                .iter()
                .filter(|(target, package)| *target != id && package.name.as_deref() == Some(&name))
                .map(|(id, _)| id)
                .collect();
            if let [target] = matches.as_slice() {
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
