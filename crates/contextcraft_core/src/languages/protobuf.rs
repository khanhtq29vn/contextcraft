//! Protocol Buffers schema outlines and repository-root-relative imports.
//!
//! Supports proto2/proto3 and editions, retaining wire types, tag numbers, reserved
//! ranges, and streaming RPC signatures. Public/weak imports use the repository
//! root by default, or literal Buf module roots. Other compiler include paths are unknown.

use tree_sitter as ts;

use super::local::{self, References};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Analysis;
use crate::repo::Repository;
use la_arena::ArenaMap;

/// Protobuf structural outlines and static local imports.
#[derive(Debug)]
pub struct Protobuf;

impl Language for Protobuf {
    fn id(&self) -> &'static str {
        "protobuf"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_proto::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/protobuf.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn resolve_packages(
        &mut self,
        _index: &Index,
        _config: &Config,
    ) -> Result<PackageResolution, Error> {
        Ok(PackageResolution::default())
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".proto"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if let Some(path) = node
            .child_by_field_name("path")
            .and_then(|node| local::literal(node, source))
            && std::path::Path::new(&path)
                .components()
                .all(|component| matches!(component, std::path::Component::Normal(_)))
        {
            references.imports.push(("import".into(), path));
        }
    }
    references
}

/// Import names are relative to the configured compiler include roots, not the importer.
/// Without compiler configuration, only the repository-root convention is supported.
fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::file_lookup(index, repository, "protobuf");
    let mut roots = Vec::new();
    for (id, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "buf.yaml" || name == "buf.work.yaml")
    }) {
        let Some(source) = repository.sources.get(id) else {
            continue;
        };
        let Ok(raw) = std::str::from_utf8(&source.bytes) else {
            continue;
        };
        let Ok(tree) = local::parse(tree_sitter_yaml::LANGUAGE.into(), raw) else {
            continue;
        };
        let base = file.path.parent().unwrap();
        let mut declared = Vec::new();
        local::visit(tree.root_node(), |node| {
            if node.kind() == "block_mapping_pair"
                && node.child_by_field_name("key").is_some_and(|key| {
                    matches!(
                        local::text(key, &source.bytes),
                        "path" | "roots" | "directories"
                    )
                })
                && let Some(value) = node.child_by_field_name("value")
            {
                local::visit(value, |node| {
                    if matches!(
                        node.kind(),
                        "plain_scalar" | "single_quote_scalar" | "double_quote_scalar"
                    ) {
                        let path = local::text(node, &source.bytes).trim_matches(['\'', '"']);
                        if let Some(path) = crate::package::local_path(index, &base.join(path)) {
                            declared.push(path);
                        }
                    }
                });
            }
        });
        if declared.is_empty() && file.path.file_name().is_some_and(|name| name == "buf.yaml") {
            declared.push(base.to_path_buf());
        }
        roots.extend(declared);
    }
    if roots.is_empty() {
        roots.push(std::path::PathBuf::new());
    }
    roots.sort();
    roots.dedup();
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        for (_, path) in &references.imports {
            let mut targets: Vec<_> = roots
                .iter()
                .filter_map(|root| local::find(index, &files, &root.join(path)))
                .collect();
            targets.sort_unstable();
            targets.dedup();
            if let [target] = targets.as_slice() {
                edges.push((file, *target));
            }
        }
    }
    local::finish(edges)
}
