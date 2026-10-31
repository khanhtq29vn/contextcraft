//! HTML structure, embedded JavaScript/CSS outlines, and literal local asset dependencies.

use tree_sitter as ts;

use super::local::{References, text};
use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::FileId;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::Analysis;
use crate::repo::Repository;
use la_arena::ArenaMap;

/// HTML tag and document outlines.
#[derive(Debug)]
pub struct Html;

impl Language for Html {
    fn id(&self) -> &'static str {
        "html"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_html::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/html.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn supplement_analysis(
        &self,
        file: FileId,
        root: ts::Node<'_>,
        source: &[u8],
        analysis: &mut Analysis,
    ) {
        local::visit(root, |node| {
            let Some(language) = embedded_language(node, source) else {
                return;
            };
            let mut parser = ts::Parser::new();
            let Ok(query) = language.query() else { return };
            let Ok(inner) =
                language.analyze(file, &mut parser, &query, &source[node.byte_range()], &())
            else {
                return;
            };
            let offset = node.start_byte();
            for (target, ranges) in [
                (&mut analysis.sigs, inner.sigs),
                (&mut analysis.skel, inner.skel),
                (&mut analysis.imports, inner.imports),
                (&mut analysis.docstrings, inner.docstrings),
            ] {
                target.extend(
                    ranges
                        .into_iter()
                        .map(|range| range.start + offset..range.end + offset),
                );
            }
        });
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
        &[".html", ".htm"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if let Some(language) = embedded_language(node, source) {
            let raw = &source[node.byte_range()];
            let Ok(raw_text) = std::str::from_utf8(raw) else {
                continue;
            };
            let Ok(tree) = local::parse(language.grammar(), raw_text) else {
                continue;
            };
            if tree.root_node().has_error() {
                continue;
            }
            let mut nodes = Vec::new();
            local::visit(tree.root_node(), |node| {
                if matches!(
                    node.kind(),
                    "import_statement" | "export_statement" | "call_expression"
                ) {
                    nodes.push(node);
                }
            });
            if language.id() == "css" {
                references
                    .imports
                    .extend(super::css::extract(&nodes, raw).imports);
            } else {
                let mut imports = Vec::new();
                for node in nodes {
                    super::javascript::dependencies::extract(node, raw, &mut imports);
                }
                references.imports.extend(
                    imports
                        .into_iter()
                        .filter(|import| {
                            import.kind == super::javascript::dependencies::ImportKind::Module
                                && (import.path.starts_with("./") || import.path.starts_with("../"))
                        })
                        .map(|import| ("script".into(), import.path)),
                );
            }
            continue;
        }
        let mut cursor = node.walk();
        let tag = node
            .named_children(&mut cursor)
            .find(|node| node.kind() == "tag_name")
            .map(|node| text(node, source).to_ascii_lowercase());
        let mut cursor = node.walk();
        for attribute in node
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "attribute")
        {
            let Some(name) = attribute.named_child(0) else {
                continue;
            };
            let name = text(name, source).to_ascii_lowercase();
            let valid = match name.as_str() {
                "src" => matches!(
                    tag.as_deref(),
                    Some(
                        "script"
                            | "img"
                            | "iframe"
                            | "audio"
                            | "video"
                            | "source"
                            | "input"
                            | "embed"
                            | "track"
                    )
                ),
                "href" => matches!(tag.as_deref(), Some("a" | "area" | "link" | "base")),
                "poster" => tag.as_deref() == Some("video"),
                "data" => tag.as_deref() == Some("object"),
                "srcset" => matches!(tag.as_deref(), Some("img" | "source")),
                _ => false,
            };
            if !valid {
                continue;
            }
            let Some(value) = attribute.named_child(1) else {
                continue;
            };
            let raw = text(value, source);
            if tag.as_deref() == Some("base") && name == "href" {
                references
                    .exports
                    .push(raw.trim_matches(['\'', '"']).to_owned());
            } else if name == "srcset" && !raw.contains("data:") {
                for candidate in raw.trim_matches(['\'', '"']).split(',') {
                    if let Some(path) = candidate
                        .split_whitespace()
                        .next()
                        .and_then(super::css::import_path)
                    {
                        references.imports.push(("asset".into(), path));
                    }
                }
            } else if !raw.contains(['&', '{', '}'])
                && let Some(path) = super::css::import_path(raw)
            {
                references.imports.push(("asset".into(), path));
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
        let mut directory = index.files[file].path.parent().unwrap().to_path_buf();
        if let Some(base) = references.exports.first() {
            let Some(path) = super::css::import_path(base) else {
                continue;
            };
            directory.push(&path);
            if !path.ends_with('/') {
                directory.pop();
            }
        }
        for (_, path) in &references.imports {
            if let Some(target) = local::find(index, &files, &directory.join(path)) {
                edges.push((file, target));
            }
        }
    }
    local::finish(edges)
}

fn embedded_language(node: ts::Node<'_>, source: &[u8]) -> Option<&'static dyn Language> {
    static JAVASCRIPT: super::javascript::JavaScript = super::javascript::JavaScript;
    static CSS: super::css::Css = super::css::Css;
    if node.kind() != "raw_text" {
        return None;
    }
    let parent = node.parent()?;
    if parent.kind() == "style_element" {
        return Some(&CSS);
    }
    if parent.kind() != "script_element" {
        return None;
    }
    let tag = parent.named_child(0)?;
    let mut cursor = tag.walk();
    for attribute in tag
        .named_children(&mut cursor)
        .filter(|node| node.kind() == "attribute")
    {
        let name = text(attribute.named_child(0)?, source);
        if name.eq_ignore_ascii_case("src") {
            return None;
        }
        if name.eq_ignore_ascii_case("type") {
            let kind = text(attribute.named_child(1)?, source)
                .trim_matches(['\'', '"'])
                .to_ascii_lowercase();
            if !matches!(
                kind.as_str(),
                "" | "module" | "text/javascript" | "application/javascript"
            ) {
                return None;
            }
        }
    }
    Some(&JAVASCRIPT)
}
