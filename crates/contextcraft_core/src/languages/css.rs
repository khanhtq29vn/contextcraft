//! CSS selector/declaration outlines and literal local stylesheet imports.
//!
//! Quoted and `url(...)` imports resolve relative to the containing stylesheet.
//! Literal asset URLs also resolve locally. Remote URLs, browser-root paths,
//! and escaped or interpolated paths remain unresolved.

use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Analysis;
use crate::repo::Repository;
use la_arena::ArenaMap;

/// Css structural outlines and static local imports.
#[derive(Debug)]
pub struct Css;

impl Language for Css {
    fn id(&self) -> &'static str {
        "css"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_css::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/css.scm")
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
        &[".css"]
    }
}

/// Literal URL paths only; browser roots and external/importer-specific schemes are unknown.
pub(super) fn import_path(value: &str) -> Option<String> {
    let value = value.trim();
    let value = if value.starts_with(['\'', '"']) {
        if value.len() < 2 || value.as_bytes().first() != value.as_bytes().last() {
            return None;
        }
        &value[1..value.len() - 1]
    } else {
        if value.chars().any(char::is_whitespace) || value.contains(['(', ')']) {
            return None;
        }
        value
    };
    if value.contains(['\\', '\0', '\r', '\n', '$', '{', '}', '\'', '"']) {
        return None;
    }
    let path = value.split(['?', '#']).next()?;
    (!path.is_empty() && !path.starts_with(['/', '~']) && !path.contains(':'))
        .then(|| path.to_owned())
}

/// Returns the path and whether the import uses CSS's `url(...)` form.
pub(super) fn import_paths(
    node: ts::Node<'_>,
    source: &[u8],
    multiple: bool,
) -> Vec<(String, bool)> {
    let mut cursor = node.walk();
    let children: Vec<_> = node
        .named_children(&mut cursor)
        .filter(|node| !matches!(node.kind(), "comment" | "js_comment"))
        .collect();
    let mut pending: Vec<_> = if multiple {
        children
    } else {
        children.into_iter().take(1).collect()
    };
    let mut paths = Vec::new();
    while let Some(node) = pending.pop() {
        if node.kind() == "string_value" {
            if let Some(path) = import_path(text(node, source)) {
                paths.push((path, false));
            }
        } else if node.kind() == "call_expression" {
            let mut cursor = node.walk();
            let children: Vec<_> = node.named_children(&mut cursor).collect();
            if children.iter().any(|node| {
                node.kind() == "function_name" && text(*node, source).eq_ignore_ascii_case("url")
            }) && let Some(arguments) = children.iter().find(|node| node.kind() == "arguments")
                && let Some(value) = text(*arguments, source)
                    .strip_prefix('(')
                    .and_then(|value| value.strip_suffix(')'))
                && let Some(path) = import_path(value)
            {
                paths.push((path, true));
            }
        } else if multiple && node.kind() == "list_value" {
            let mut cursor = node.walk();
            pending.extend(node.named_children(&mut cursor));
        }
    }
    paths
}

pub(super) fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "call_expression" {
            if let Some(arguments) = node.named_child(1)
                && let Some(raw) = text(arguments, source)
                    .strip_prefix('(')
                    .and_then(|raw| raw.strip_suffix(')'))
                && let Some(path) = import_path(raw)
            {
                references.imports.push(("asset".into(), path));
            }
            continue;
        }
        references.imports.extend(
            import_paths(node, source, false)
                .into_iter()
                .map(|(path, _)| ("import".into(), path)),
        );
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
        for (_, path) in &references.imports {
            if let Some(target) = local::find(
                index,
                &files,
                &index.files[file].path.parent().unwrap().join(path),
            ) {
                edges.push((file, target));
            }
        }
    }
    local::finish(edges)
}
