//! Scala outlines, literal sbt projects, and local namespace imports.
//!
//! Supports Scala 2/3 outlines, sbt `project`/`Project` declarations, literal source
//! directories, and `dependsOn`. Aggregation records membership, not dependencies.
//! Arbitrary sbt code, plugins, Mill/Gradle builds, and compiler-level symbol binding
//! are not evaluated.

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

/// Scala grammar and local project analysis.
#[derive(Debug)]
pub struct Scala;

impl Language for Scala {
    fn id(&self) -> &'static str {
        "scala"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_scala::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/scala.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn discover_packages(
        &self,
        index: &Index,
        config: &Config,
    ) -> Result<Vec<crate::package::Package>, Error> {
        manifest::packages(index, config)
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
        &["!**/.bsp/**", "!**/.metals/**", "!**/.scala-build/**"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["build.sbt"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["build.sbt", "build.properties", "plugins.sbt"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".scala", ".sc"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();

    for &node in nodes {
        if node.kind() == "import_declaration" {
            let value = text(node, source)
                .trim_start_matches("import")
                .trim()
                .trim_end_matches(';');
            if let Some((base, selectors)) = value.split_once('{') {
                let base = base
                    .trim()
                    .trim_end_matches('.')
                    .trim_start_matches("_root_.");
                for selector in selectors.trim_end_matches('}').split(',') {
                    let renamed = selector
                        .split_once("=>")
                        .or_else(|| selector.split_once(" as "));
                    if renamed.is_some_and(|(_, alias)| alias.trim() == "_") {
                        continue;
                    }
                    let selector = renamed
                        .map_or(selector, |(name, _)| name)
                        .split_whitespace()
                        .next()
                        .unwrap_or("");
                    if matches!(selector, "_" | "*" | "given") {
                        references.imports.push(("namespace".into(), base.into()));
                    } else if !selector.is_empty() {
                        references
                            .imports
                            .push(("type".into(), format!("{base}.{selector}")));
                    }
                }
            } else {
                for item in value.split(',') {
                    let item = item
                        .split_whitespace()
                        .next()
                        .unwrap_or("")
                        .trim_start_matches("_root_.");
                    let wildcard =
                        item.ends_with("._") || item.ends_with(".*") || item.ends_with(".given");
                    references.imports.push((
                        if wildcard { "namespace" } else { "type" }.into(),
                        if wildcard {
                            item.rsplit_once('.').unwrap().0
                        } else {
                            item
                        }
                        .into(),
                    ));
                }
            }
            continue;
        }

        let Some(name) = node
            .child_by_field_name("name")
            .or_else(|| node.child_by_field_name("pattern"))
        else {
            continue;
        };
        let mut parts = vec![text(name, source).to_owned()];
        let mut local = false;
        let mut parent = node.parent();
        while let Some(ancestor) = parent {
            local |= matches!(ancestor.kind(), "function_definition" | "lambda_expression");
            if matches!(
                ancestor.kind(),
                "package_clause" | "object_definition" | "class_definition" | "trait_definition"
            ) && let Some(name) = ancestor.child_by_field_name("name")
            {
                parts.push(text(name, source).into());
            }
            let mut cursor = ancestor.walk();
            let prefixes: Vec<_> = ancestor
                .named_children(&mut cursor)
                .filter(|sibling| {
                    sibling.kind() == "package_clause"
                        && sibling.child_by_field_name("body").is_none()
                        && sibling.end_byte() <= node.start_byte()
                })
                .filter_map(|sibling| sibling.child_by_field_name("name"))
                .map(|name| text(name, source).to_owned())
                .collect();
            parts.extend(prefixes.into_iter().rev());
            parent = ancestor.parent();
        }
        parts.reverse();
        if !local {
            references.exports.push(parts.join("."));
        }
    }

    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    local::resolve_symbols(index, repository, references)
}
