//! Ruby `.rb` outlines, local Bundler gems, and literal load dependencies.
//!
//! Reads literal gemspec names/load paths and Gemfile path dependencies without
//! executing Ruby. Resolves `require_relative`, local-gem `require`, and literal
//! repository-relative `load`. Dynamic load paths and metaprogramming remain unresolved.

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
use local::{References, text};

/// Ruby grammar and local project analysis.
#[derive(Debug)]
pub struct Ruby;

impl Language for Ruby {
    fn id(&self) -> &'static str {
        "ruby"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_ruby::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/ruby.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn discover_packages(
        &self,
        index: &Index,
        _config: &Config,
    ) -> Result<Vec<crate::package::Package>, Error> {
        Ok(local::discover(index, "ruby", &["gemspec"], &["Gemfile"]))
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
        &["!**/vendor/bundle/**", "!**/.bundle/**", "!**/Gemfile.lock"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["Gemfile"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".rb"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();

    for &node in nodes {
        if node
            .child_by_field_name("receiver")
            .is_some_and(|receiver| text(receiver, source) != "Kernel")
        {
            continue;
        }
        let Some(method) = node.child_by_field_name("method") else {
            continue;
        };
        let Some(arguments) = node.child_by_field_name("arguments") else {
            continue;
        };
        let Some(argument) = arguments.named_child(u32::from(text(method, source) == "autoload"))
        else {
            continue;
        };

        if let Some(path) = local::literal(argument, source) {
            references.imports.push((text(method, source).into(), path));
        }
    }

    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::file_lookup(index, repository, "ruby");
    let mut edges = Vec::new();
    let indexed: std::collections::HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    let mut load_paths = std::collections::HashMap::new();
    for (id, package) in index.packages.iter() {
        let mut paths = vec![package.root.join("lib")];
        for manifest in package.manifests.iter().filter(|path| {
            path.extension()
                .is_some_and(|extension| extension == "gemspec")
        }) {
            let Some(source) = indexed
                .get(manifest.as_path())
                .and_then(|&file| repository.sources.get(file))
            else {
                continue;
            };
            let Ok(tree) = local::parse(
                tree_sitter_ruby::LANGUAGE.into(),
                std::str::from_utf8(&source.bytes).unwrap_or(""),
            ) else {
                continue;
            };
            local::visit(tree.root_node(), |node| {
                if node.kind() != "assignment" {
                    return;
                }
                let Some(left) = node.child_by_field_name("left") else {
                    return;
                };
                let Some(right) = node.child_by_field_name("right") else {
                    return;
                };
                if !text(left, &source.bytes).ends_with(".require_paths") || right.kind() != "array"
                {
                    return;
                }
                let mut cursor = right.walk();
                let values: Vec<_> = right
                    .named_children(&mut cursor)
                    .map(|node| local::literal(node, &source.bytes))
                    .collect();
                if values.iter().all(Option::is_some) {
                    paths = values
                        .into_iter()
                        .flatten()
                        .map(|path| package.root.join(path))
                        .collect();
                }
            });
        }
        load_paths.insert(id, paths);
    }

    for (file, references) in references.iter() {
        for (kind, path) in &references.imports {
            let mut bases = Vec::new();
            if kind == "require_relative" {
                bases.push(index.files[file].path.parent().unwrap().to_path_buf());
            } else if kind == "load" || path.starts_with("./") || path.starts_with("../") {
                bases.push(std::path::PathBuf::new());
            } else {
                for package in local::visible(index, index.files[file].package_id) {
                    bases.extend(load_paths[&package].iter().cloned());
                }
            }

            let mut targets = Vec::new();
            for base in bases {
                let path = base.join(path);
                let target = local::find(index, &files, &path).or_else(|| {
                    (kind != "load" && path.extension().is_none())
                        .then(|| {
                            let mut name = path.as_os_str().to_os_string();
                            name.push(".rb");
                            local::find(index, &files, std::path::Path::new(&name))
                        })
                        .flatten()
                });
                if let Some(target) = target {
                    targets.push(target);
                }
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
