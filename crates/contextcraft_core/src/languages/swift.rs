//! Swift outlines, local SwiftPM targets/products, and Xcode project/workspace metadata.
//!
//! Resolves module imports through explicit local target dependencies and source
//! membership. SwiftPM manifests are inspected, never executed. Dynamic manifests,
//! generated sources, remote package fetching, and compiler-level name binding are
//! not evaluated.

use tree_sitter as ts;

pub mod manifest;
pub mod xcode;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::FileId;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};
use la_arena::ArenaMap;
use local::{References, text};

/// Swift grammar and local project analysis.
#[derive(Debug)]
pub struct Swift;

impl Language for Swift {
    fn id(&self) -> &'static str {
        "swift"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_swift::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/swift.scm")
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
        &[
            "!**/.build/**",
            "!**/DerivedData/**",
            "!**/Carthage/Build/**",
            "!**/Pods/**",
            "!**/Package.resolved",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["Package.swift", "project.pbxproj"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "Package.swift",
            "Package.resolved",
            "project.pbxproj",
            "contents.xcworkspacedata",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".swift"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        let declaration = text(node, source);
        let Some((_, import)) = declaration.split_once("import") else {
            continue;
        };
        let import = import.trim().trim_end_matches(';');
        let name = import
            .split_whitespace()
            .last()
            .unwrap_or("")
            .split('.')
            .next()
            .unwrap_or("");
        if !name.is_empty() {
            references.imports.push(("module".into(), name.into()));
        }
    }
    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::file_lookup(index, repository, "swift");
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        let package = index.files[file].package_id;
        for (_, module) in &references.imports {
            for dependency in &index.packages[package].dependencies {
                let target = &index.packages[dependency.package];
                if target.name.as_deref() != Some(module) {
                    continue;
                }
                for &target in &target.targets {
                    if files.contains_key(index.files[target].path.as_path()) {
                        edges.push((file, target));
                    }
                }
            }
        }
    }
    edges.extend(xcode::resolve(index, repository, references));
    local::finish(edges)
}
