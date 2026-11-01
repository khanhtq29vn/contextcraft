//! Java outlines, shared JVM projects, and static local type imports.
//!
//! Maven and literal Gradle metadata establish project visibility. Build plugins,
//! annotation processing, reflection, and compiler-level overload binding are not evaluated.

use std::path::PathBuf;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::{Package, PackageResolution};
use crate::repo::{Analysis, Repository};

pub mod manifest;

/// Java grammar with Maven and shared Gradle project ownership.
#[derive(Debug)]
pub struct Java;

impl Language for Java {
    fn id(&self) -> &'static str {
        "java"
    }

    fn package_language(&self) -> &'static str {
        "jvm"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_java::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/java.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn discover_packages(&self, index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
        super::jvm::packages(index, config)
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        super::jvm::discover(index, config)
    }

    fn supplement_analysis(
        &self,
        _file: FileId,
        root: ts::Node<'_>,
        _source: &[u8],
        analysis: &mut Analysis,
    ) {
        local::visit(root, |node| {
            if !matches!(node.kind(), "field_declaration" | "constant_declaration") {
                return;
            }
            let mut cursor = node.walk();
            let mut first = true;
            for element in node
                .named_children(&mut cursor)
                .filter(|node| matches!(node.kind(), "variable_declarator"))
            {
                if let Some(name) = element.child_by_field_name("name") {
                    let range = if first {
                        node.start_byte()..name.end_byte()
                    } else {
                        name.byte_range()
                    };
                    analysis.sigs.push(range.clone());
                    analysis.skel.push(range);
                    first = false;
                }
            }
        });
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &["!**/*.class", "!**/*.jar", "!**/.gradle/**"]
    }

    fn ignored_directories(&self, paths: &[PathBuf]) -> Vec<PathBuf> {
        paths
            .iter()
            .filter_map(|path| {
                let name = path.file_name()?;
                if name == "build.gradle" || name == "build.gradle.kts" {
                    Some(path.parent()?.join("build"))
                } else if name == "pom.xml" {
                    Some(path.parent()?.join("target"))
                } else {
                    None
                }
            })
            .collect()
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "gradle.properties",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".java"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let package = nodes
        .iter()
        .find(|node| node.kind() == "package_declaration")
        .and_then(|node| {
            let mut cursor = node.walk();
            node.named_children(&mut cursor)
                .find(|node| matches!(node.kind(), "identifier" | "scoped_identifier"))
        })
        .map(|node| text(node, source))
        .unwrap_or("");
    for &node in nodes {
        if node.has_error() {
            continue;
        }
        match node.kind() {
            "import_declaration" => {
                let mut cursor = node.walk();
                if let Some(name) = node
                    .named_children(&mut cursor)
                    .find(|node| matches!(node.kind(), "identifier" | "scoped_identifier"))
                {
                    let mut value = text(name, source);
                    let mut cursor = node.walk();
                    let wildcard = node
                        .named_children(&mut cursor)
                        .any(|node| node.kind() == "asterisk");
                    let mut cursor = node.walk();
                    let is_static = node
                        .children(&mut cursor)
                        .any(|node| node.kind() == "static");
                    if is_static {
                        if !wildcard {
                            value = value.rsplit_once('.').map_or(value, |(owner, _)| owner);
                        }
                        references.imports.push(("type".into(), value.into()));
                    } else {
                        references.imports.push((
                            if wildcard { "package" } else { "type" }.into(),
                            value.into(),
                        ));
                    }
                }
            }
            "type_identifier" | "scoped_type_identifier" => {
                let value = text(node, source);
                references.imports.push((
                    "type".into(),
                    if value.contains('.') || package.is_empty() {
                        value.into()
                    } else {
                        format!("{package}.{value}")
                    },
                ));
            }
            "class_declaration"
            | "interface_declaration"
            | "enum_declaration"
            | "record_declaration"
            | "annotation_type_declaration" => {
                let Some(name) = node.child_by_field_name("name") else {
                    continue;
                };
                let mut parts = vec![text(name, source)];
                let mut parent = node.parent();
                let mut local = false;
                while let Some(ancestor) = parent {
                    if matches!(
                        ancestor.kind(),
                        "block" | "constructor_body" | "lambda_expression"
                    ) {
                        local = true;
                        break;
                    }
                    if matches!(
                        ancestor.kind(),
                        "class_declaration"
                            | "interface_declaration"
                            | "enum_declaration"
                            | "record_declaration"
                            | "annotation_type_declaration"
                    ) && let Some(name) = ancestor.child_by_field_name("name")
                    {
                        parts.push(text(name, source));
                    }
                    parent = ancestor.parent();
                }
                if !local {
                    if !package.is_empty() {
                        parts.push(package);
                    }
                    parts.reverse();
                    references.exports.push(parts.join("."));
                }
            }
            _ => {}
        }
    }
    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    super::jvm::resolve(index, repository, references, "java")
}
