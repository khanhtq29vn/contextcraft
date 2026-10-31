//! Rust parsing, Cargo workspace discovery, and local module resolution.

use std::sync::{Arc, Mutex};

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::{PackageDependency, PackageResolution};
use crate::repo::Repository;

pub mod dependencies;
pub mod manifest;
pub mod resolve;

/// Rust grammar with repository-local Cargo target and dependency metadata.
#[derive(Debug, Default)]
pub struct Rust {
    packages: Arc<ArenaMap<PackageId, manifest::RustPackage>>,
}

impl Language for Rust {
    fn id(&self) -> &'static str {
        "rust"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_rust::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/rust.scm")
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        let (packages, workspaces) = manifest::discover(index, config)?;
        let mut resolved = ArenaMap::new();

        for (id, metadata) in packages.iter() {
            let mut package = index.packages[id].clone();
            package.name = Some(metadata.name.clone());
            package.targets = metadata.targets.iter().map(|target| target.root).collect();
            package.targets.sort_unstable();
            package.targets.dedup();

            for dependency in &metadata.dependencies {
                let dependency = PackageDependency {
                    alias: dependency.alias.clone(),
                    package: dependency.package,
                };

                if !package.dependencies.contains(&dependency) {
                    package.dependencies.push(dependency);
                }
            }

            resolved.insert(id, package);
        }

        self.packages = Arc::new(packages);

        Ok(PackageResolution {
            packages: resolved,
            workspaces,
        })
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(RustAnalysis {
            packages: Arc::clone(&self.packages),
            dependencies: Mutex::new(ArenaMap::new()),
        })
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &["!**/target/**", "!**/Cargo.lock"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["Cargo.toml"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["Cargo.toml", "Cargo.lock"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".rs"]
    }
}

#[derive(Debug)]
struct RustAnalysis {
    packages: Arc<ArenaMap<PackageId, manifest::RustPackage>>,
    dependencies: Mutex<ArenaMap<FileId, dependencies::RustDependencies>>,
}

impl LanguageAnalysis for RustAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut dependencies = dependencies::RustDependencies::default();

        for &node in nodes {
            dependencies::extract(node, source, &mut dependencies);
        }

        self.dependencies.lock().unwrap().insert(file, dependencies);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let dependencies = self.dependencies.lock().unwrap();

        let mut edges = resolve::resolve(index, &self.packages, &dependencies);
        let files = super::local::readable_files(index, repository);
        for (file, references) in dependencies.iter() {
            for path in &references.includes {
                if let Some(target) = super::local::find(
                    index,
                    &files,
                    &index.files[file].path.parent().unwrap().join(path),
                ) {
                    edges.push((file, target));
                }
            }
        }
        super::local::finish(edges)
    }
}
