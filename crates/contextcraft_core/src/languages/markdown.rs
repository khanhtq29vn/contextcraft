//! Markdown document outlines and literal local links/assets.

use tree_sitter as ts;

use super::local::{References, text};
use super::{Language, LanguageAnalysis, local};
use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::package::PackageResolution;

/// Markdown block grammar for heading and documentation outlines.
#[derive(Debug)]
pub struct Markdown;

impl Language for Markdown {
    fn id(&self) -> &'static str {
        "markdown"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_md::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/markdown.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(
            extract,
            local::resolve_relative,
        ))
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
        &[".md", ".markdown", ".mdown", ".mkd", ".mkdn"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "link_destination" {
            if let Some(path) = super::css::import_path(text(node, source).trim_matches(['<', '>']))
            {
                references.imports.push(("link".into(), path));
            }
            continue;
        }
        let raw = text(node, source);
        let Ok(tree) = local::parse(tree_sitter_md::INLINE_LANGUAGE.into(), raw) else {
            continue;
        };
        local::visit(tree.root_node(), |node| {
            if node.kind() == "link_destination"
                && let Some(path) =
                    super::css::import_path(text(node, raw.as_bytes()).trim_matches(['<', '>']))
            {
                references.imports.push(("link".into(), path));
            }
        });
    }
    references
}
