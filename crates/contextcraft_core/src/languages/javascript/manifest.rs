//! Discover local npm and pnpm package/workspace relationships.

use std::collections::HashMap;

use serde_json::Value;

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution, Workspace, local_path};

/// Reads static package names, workspace membership, and local dependencies.
///
/// # Errors
///
/// Returns an error if a readable package manifest is invalid.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut documents = HashMap::new();
    for (id, package) in index.packages.iter() {
        if package.language != Some("javascript") {
            continue;
        }
        let manifest = package.root.join("package.json");
        let document: Value = if package.manifests.contains(&manifest) {
            let Some(text) = local::read(index, &manifest, config)? else {
                continue;
            };
            serde_json::from_str(&text).map_err(|error| Error::Manifest {
                path: manifest.clone(),
                message: error.to_string(),
            })?
        } else {
            Value::Object(Default::default())
        };
        if !document.is_object() {
            return Err(Error::Manifest {
                path: manifest,
                message: "package.json must contain an object".into(),
            });
        }
        let mut package = package.clone();
        package.name = document
            .get("name")
            .and_then(Value::as_str)
            .map(str::to_owned);
        resolution.packages.insert(id, package);
        documents.insert(id, document);
    }

    for (id, document) in &documents {
        let package = &resolution.packages[*id];
        let mut patterns: Vec<String> = document
            .get("workspaces")
            .and_then(|value| {
                value
                    .as_array()
                    .or_else(|| value.get("packages").and_then(Value::as_array))
            })
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect();
        let pnpm = package.root.join("pnpm-workspace.yaml");
        if index.files.iter().any(|(_, file)| file.path == pnpm)
            && let Some(text) = local::read(index, &pnpm, config)?
        {
            let tree = local::parse(tree_sitter_yaml::LANGUAGE.into(), &text)?;
            local::visit(tree.root_node(), |node| {
                if node.kind() == "block_mapping_pair"
                    && node
                        .child_by_field_name("key")
                        .is_some_and(|key| local::text(key, text.as_bytes()) == "packages")
                    && let Some(value) = node.child_by_field_name("value")
                {
                    local::visit(value, |node| {
                        if matches!(
                            node.kind(),
                            "plain_scalar" | "single_quote_scalar" | "double_quote_scalar"
                        ) {
                            patterns.push(
                                local::text(node, text.as_bytes())
                                    .trim_matches(['\'', '"'])
                                    .to_owned(),
                            );
                        }
                    });
                }
            });
        }
        if patterns.is_empty() {
            continue;
        }
        let globs: Vec<_> = patterns
            .iter()
            .filter_map(|pattern| {
                let negative = pattern.starts_with('!');
                let pattern = pattern.strip_prefix('!').unwrap_or(pattern);
                local::path_glob(&package.root, pattern.trim_end_matches('/'))
                    .map(|glob| (negative, glob))
            })
            .collect();
        let mut members: Vec<_> = resolution
            .packages
            .iter()
            .filter(|(_, member)| {
                globs
                    .iter()
                    .any(|(negative, glob)| !negative && glob.is_match(&member.root))
                    && !globs
                        .iter()
                        .any(|(negative, glob)| *negative && glob.is_match(&member.root))
            })
            .map(|(id, _)| id)
            .collect();
        members.push(*id);
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: package.root.clone(),
            language: "javascript",
            members,
        });
    }
    resolution.workspaces.sort_by(|a, b| a.root.cmp(&b.root));

    for (id, document) in &documents {
        let root = resolution.packages[*id].root.clone();
        let mut dependencies = Vec::new();
        for field in [
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "optionalDependencies",
        ] {
            for (alias, version) in document
                .get(field)
                .and_then(Value::as_object)
                .into_iter()
                .flatten()
            {
                let Some(version) = version.as_str() else {
                    continue;
                };
                let explicit = version
                    .strip_prefix("file:")
                    .or_else(|| version.strip_prefix("link:"))
                    .and_then(|path| local_path(index, &root.join(path)));
                let workspace = resolution
                    .workspaces
                    .iter()
                    .filter(|workspace| workspace.members.contains(id))
                    .max_by_key(|workspace| workspace.root.components().count());
                let requested = version
                    .strip_prefix("workspace:")
                    .and_then(|specifier| specifier.rsplit_once('@').map(|(name, _)| name))
                    .filter(|name| !name.is_empty())
                    .unwrap_or(alias);
                let targets: Vec<_> = resolution
                    .packages
                    .iter()
                    .filter(|(target, package)| {
                        if let Some(path) = &explicit {
                            return package.root == *path;
                        }
                        if version.starts_with("file:") || version.starts_with("link:") {
                            return false;
                        }
                        let matches_version = version.starts_with("workspace:")
                            || documents
                                .get(target)
                                .and_then(|document| document.get("version"))
                                .and_then(Value::as_str)
                                .and_then(|value| semver::Version::parse(value).ok())
                                .is_some_and(|value| {
                                    let requirement = if semver::Version::parse(version).is_ok() {
                                        format!("={version}")
                                    } else {
                                        version.to_owned()
                                    };
                                    semver::VersionReq::parse(&requirement)
                                        .is_ok_and(|requirement| requirement.matches(&value))
                                });
                        workspace.is_some_and(|workspace| workspace.members.contains(target))
                            && package.name.as_deref() == Some(requested)
                            && matches_version
                    })
                    .map(|(id, _)| id)
                    .collect();
                if let [target] = targets.as_slice()
                    && target != id
                {
                    dependencies.push(PackageDependency {
                        alias: alias.clone(),
                        package: *target,
                    });
                }
            }
        }
        dependencies.sort_by(|a, b| a.alias.cmp(&b.alias).then(a.package.cmp(&b.package)));
        dependencies.dedup();
        resolution.packages[*id].dependencies = dependencies;
    }
    Ok(resolution)
}

/// Parses JSONC manifests without changing comment-like text inside strings.
pub(super) fn json_config(source: &[u8]) -> Option<Value> {
    let mut bytes = source.to_vec();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'"' {
            i += 1;
            while i < bytes.len() {
                if bytes[i] == b'\\' {
                    i += 2;
                } else if bytes[i] == b'"' {
                    i += 1;
                    break;
                } else {
                    i += 1;
                }
            }
        } else if bytes.get(i..i + 2) == Some(b"//") {
            while i < bytes.len() && bytes[i] != b'\n' {
                bytes[i] = b' ';
                i += 1;
            }
        } else if bytes.get(i..i + 2) == Some(b"/*") {
            bytes[i..i + 2].fill(b' ');
            i += 2;
            while i + 1 < bytes.len() && &bytes[i..i + 2] != b"*/" {
                bytes[i] = b' ';
                i += 1;
            }
            if i + 1 >= bytes.len() {
                return None;
            }
            bytes[i..i + 2].fill(b' ');
            i += 2;
        } else {
            i += 1;
        }
    }
    i = 0;
    let mut string = false;
    while i < bytes.len() {
        if bytes[i] == b'\\' && string {
            i += 2;
            continue;
        }
        if bytes[i] == b'"' {
            string = !string;
        }
        if !string && bytes[i] == b',' {
            let next = bytes[i + 1..]
                .iter()
                .find(|byte| !byte.is_ascii_whitespace());
            if matches!(next, Some(b']' | b'}')) {
                bytes[i] = b' ';
            }
        }
        i += 1;
    }
    serde_json::from_slice(&bytes).ok()
}
