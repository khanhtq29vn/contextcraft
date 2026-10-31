//! Lua outlines, LuaRocks metadata, and static local module dependencies.
//!
//! Resolves literal `require`, `dofile`, and `loadfile` calls. Module lookup uses
//! declared rockspec mappings and conventional root, `src`, and `lua` directories.
//! Runtime changes to `package.path`, custom loaders, and executable rockspec logic
//! are not evaluated. Local rock names must be unambiguous.

use tree_sitter as ts;

pub mod manifest;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::FileId;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};
use la_arena::ArenaMap;
use local::{References, text, visit};

/// Lua grammar and local project analysis.
#[derive(Debug)]
pub struct Lua;

impl Language for Lua {
    fn id(&self) -> &'static str {
        "lua"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_lua::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/lua.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn discover_packages(
        &self,
        index: &Index,
        _config: &Config,
    ) -> Result<Vec<crate::package::Package>, Error> {
        Ok(local::discover(index, "lua", &["rockspec"], &[]))
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        manifest::discover(index, config)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &["!**/lua_modules/**"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".lua"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();

    for &node in nodes {
        let Some(name) = node.child_by_field_name("name") else {
            continue;
        };
        let Some(arguments) = node.child_by_field_name("arguments") else {
            continue;
        };
        let Some(argument) = arguments.named_child(0) else {
            continue;
        };
        let value = local::literal(argument, source).or_else(|| {
            (argument.kind() == "string" && text(argument, source).starts_with("[[")).then(|| {
                text(argument, source)
                    .trim_start_matches("[[")
                    .trim_end_matches("]]")
                    .to_owned()
            })
        });

        if let Some(value) = value {
            references.imports.push((text(name, source).into(), value));
        }
    }

    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::file_lookup(index, repository, "lua");
    let mut edges = Vec::new();
    let mut declared =
        std::collections::HashMap::<_, std::collections::HashMap<String, Vec<FileId>>>::new();
    let indexed: std::collections::HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();

    for (package, metadata) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("lua"))
    {
        for manifest in &metadata.manifests {
            let Some(source) = indexed
                .get(manifest.as_path())
                .and_then(|&id| repository.sources.get(id))
            else {
                continue;
            };
            let Ok(tree) = local::parse(
                tree_sitter_lua::LANGUAGE.into(),
                std::str::from_utf8(&source.bytes).unwrap_or(""),
            ) else {
                continue;
            };
            visit(tree.root_node(), |node| {
                if node.kind() != "field" {
                    return;
                }
                let Some(name) = node.child_by_field_name("name") else {
                    return;
                };
                let Some(value) = node.child_by_field_name("value") else {
                    return;
                };
                let Some(modules) = node.parent().and_then(|node| node.parent()) else {
                    return;
                };
                if modules.kind() != "field"
                    || modules
                        .child_by_field_name("name")
                        .is_none_or(|name| text(name, &source.bytes) != "modules")
                {
                    return;
                }
                let Some(build) = modules
                    .parent()
                    .and_then(|node| node.parent())
                    .and_then(|node| node.parent())
                else {
                    return;
                };
                if build.kind() != "assignment_statement"
                    || build
                        .named_child(0)
                        .is_none_or(|node| text(node, &source.bytes) != "build")
                {
                    return;
                }
                let module = local::literal(name, &source.bytes).or_else(|| {
                    (name.kind() == "identifier").then(|| text(name, &source.bytes).to_owned())
                });
                if let Some(module) = module
                    && let Some(value) = local::literal(value, &source.bytes)
                    && let Some(target) = local::find(index, &files, &metadata.root.join(value))
                {
                    declared
                        .entry(package)
                        .or_default()
                        .entry(module)
                        .or_default()
                        .push(target);
                }
            });
        }
    }

    for (file, references) in references.iter() {
        let packages = local::visible(index, index.files[file].package_id);

        for (kind, path) in &references.imports {
            let mut targets = Vec::new();

            if kind == "require" {
                if path.contains(['/', '\\']) {
                    continue;
                }
                let module = path.replace('.', "/");

                for &package in &packages {
                    let root = &index.packages[package].root;
                    if let Some(modules) =
                        declared.get(&package).and_then(|modules| modules.get(path))
                    {
                        targets.extend(modules);
                    } else {
                        for prefix in ["", "src", "lua"] {
                            for suffix in [format!("{module}.lua"), format!("{module}/init.lua")] {
                                if let Some(target) =
                                    local::find(index, &files, &root.join(prefix).join(suffix))
                                {
                                    targets.push(target);
                                }
                            }
                        }
                    }
                }
            } else if let Some(target) = local::find(index, &files, std::path::Path::new(path)) {
                targets.push(target);
            }

            targets.sort_unstable();
            targets.dedup();
            if let [target] = targets.as_slice() {
                edges.push((file, *target));
            }
        }
    }

    local::finish(edges)
}
