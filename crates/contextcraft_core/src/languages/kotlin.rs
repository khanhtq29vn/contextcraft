//! Kotlin outlines, literal Gradle projects, and local package-qualified imports.
//!
//! Supports static project includes, directory mappings, and project dependencies
//! in Kotlin and Groovy Gradle DSL files. Build logic, composite builds, plugins,
//! custom source sets, and compiler-level symbol binding are not evaluated.

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis, local, render_outline};

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};

mod dependencies;
pub mod manifest;

/// Kotlin grammar for `.kt` sources and `.kts` scripts.
#[derive(Debug)]
pub struct Kotlin;

impl Language for Kotlin {
    fn id(&self) -> &'static str {
        "kotlin"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_kotlin_ng::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/kotlin.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(
            dependencies::extract,
            resolve,
        ))
    }

    fn supplement_analysis(
        &self,
        _file: FileId,
        root: ts::Node<'_>,
        _source: &[u8],
        analysis: &mut Analysis,
    ) {
        local::visit(root, |node| {
            let bodies: &[&str] = match node.kind() {
                "class_declaration" | "object_declaration" | "companion_object" | "enum_entry" => {
                    &["class_body", "enum_class_body"]
                }
                "function_declaration" | "getter" | "setter" => &["function_body"],
                "secondary_constructor" => &["block"],
                "property_declaration" => &["=", "property_delegate", "getter", "setter"],
                "type_alias" => &[],
                _ => return,
            };

            let mut parent = node.parent();
            while let Some(ancestor) = parent {
                if matches!(
                    ancestor.kind(),
                    "function_body" | "block" | "lambda_literal"
                ) {
                    return;
                }
                parent = ancestor.parent();
            }

            // Bodies are child nodes, not fields; bodyless declarations keep their full range.
            let mut cursor = node.walk();
            let end = node
                .children(&mut cursor)
                .find(|child| bodies.contains(&child.kind()))
                .map_or(node.end_byte(), |body| body.start_byte());
            let header = node.start_byte()..end;
            analysis.sigs.push(header.clone());
            analysis.skel.push(header);
        });
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
        &["!**/.gradle/**", "!**/.kotlin/**"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["build.gradle", "build.gradle.kts"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "gradle.properties",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".kt", ".kts"]
    }
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, local::References>,
) -> Vec<(FileId, FileId)> {
    local::resolve_symbols(index, repository, references)
}
