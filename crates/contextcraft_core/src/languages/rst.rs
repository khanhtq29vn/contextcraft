//! reStructuredText outlines and literal local include dependencies.
//!
//! Relative `include` and Sphinx `literalinclude` paths are resolved against the
//! containing document. Sphinx toctrees and image/figure paths also produce edges.
//! Absolute paths, built-in includes, and URLs are not resolved.

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};

/// reStructuredText document outlines.
#[derive(Debug)]
pub struct Rst;

impl Language for Rst {
    fn id(&self) -> &'static str {
        "rst"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_rst::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/rst.scm")
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
        &[".rst", ".rest"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        let Some(name) = node.child_by_field_name("name") else {
            continue;
        };
        if !matches!(
            text(name, source),
            "include" | "literalinclude" | "image" | "figure" | "toctree"
        ) {
            continue;
        }
        let Some(body) = node.child_by_field_name("body") else {
            continue;
        };
        if text(name, source) == "toctree" {
            let mut cursor = body.walk();
            for content in body
                .named_children(&mut cursor)
                .filter(|node| node.kind() == "content")
            {
                for line in text(content, source).lines() {
                    let line = line.trim();
                    let path = line
                        .rsplit_once('<')
                        .and_then(|(_, path)| path.strip_suffix('>'))
                        .unwrap_or(line);
                    if !path.is_empty()
                        && !path.starts_with(['/', '~', ':'])
                        && !path.contains("://")
                        && path != "self"
                    {
                        references.imports.push(("toctree".into(), path.into()));
                    }
                }
            }
            continue;
        }
        let mut cursor = body.walk();
        if let Some(argument) = body
            .named_children(&mut cursor)
            .find(|node| node.kind() == "arguments")
        {
            let path = text(argument, source).trim();
            if !path.is_empty()
                && !path.starts_with(['/', '<', '~'])
                && !path.contains(['\n', '\r', '\0'])
                && !path.contains("://")
            {
                references.imports.push(("include".into(), path.into()));
            }
        }
    }
    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::readable_files(index, repository);
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        for (kind, path) in &references.imports {
            if let Some(target) = local::find(
                index,
                &files,
                &index.files[file].path.parent().unwrap().join(path),
            ) {
                edges.push((file, target));
            } else if kind == "toctree" {
                let base = index.files[file].path.parent().unwrap();
                for extension in ["rst", "md"] {
                    let path = format!("{path}.{extension}");
                    if let Some(target) = local::find(index, &files, &base.join(&path)) {
                        edges.push((file, target));
                    } else if path.contains(['*', '?', '['])
                        && let Some(glob) = local::path_glob(base, &path)
                    {
                        edges.extend(
                            files
                                .iter()
                                .filter(|(path, _)| glob.is_match(path))
                                .map(|(_, target)| (file, *target)),
                        );
                    }
                }
            }
        }
    }
    local::finish(edges)
}
