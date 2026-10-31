//! Go parsing, module discovery, and local import resolution.

use std::sync::{Arc, Mutex};

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::PackageResolution;
use crate::repo::Repository;

pub mod dependencies;
pub mod manifest;
pub mod resolve;

/// Go grammar with repository-local module metadata.
#[derive(Debug, Default)]
pub struct Go {
    packages: Arc<ArenaMap<PackageId, manifest::GoPackage>>,
}

impl Language for Go {
    fn id(&self) -> &'static str {
        "go"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_go::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/go.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(GoAnalysis {
            packages: Arc::clone(&self.packages),
            dependencies: Mutex::new(ArenaMap::new()),
        })
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        let (resolution, packages) = manifest::discover(index, config)?;
        self.packages = Arc::new(packages);

        Ok(resolution)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/vendor/**",
            "!**/go.sum",
            "!**/go.work.sum",
            "!**/*.test",
            "!**/coverage.out",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["go.mod"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["go.mod", "go.sum", "go.work", "go.work.sum"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".go"]
    }
}

#[derive(Debug)]
struct GoAnalysis {
    packages: Arc<ArenaMap<PackageId, manifest::GoPackage>>,
    dependencies: Mutex<ArenaMap<FileId, dependencies::Dependencies>>,
}

impl LanguageAnalysis for GoAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut dependencies = dependencies::Dependencies::default();

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
        edges.extend(resolve::embeds(index, repository, &dependencies));
        super::local::finish(edges)
    }
}
