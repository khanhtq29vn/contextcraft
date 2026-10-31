//! C parsing and local include resolution with static compilation-database paths.

use std::sync::Mutex;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Repository;

pub mod dependencies;
pub mod resolve;

/// C grammar and quoted-include analysis.
#[derive(Debug)]
pub struct C;

impl Language for C {
    fn id(&self) -> &'static str {
        "c"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_c::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/c.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(CAnalysis::default())
    }

    fn resolve_packages(
        &mut self,
        _index: &Index,
        _config: &Config,
    ) -> Result<PackageResolution, Error> {
        Ok(PackageResolution::default())
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/*.o",
            "!**/*.obj",
            "!**/*.a",
            "!**/*.lib",
            "!**/*.so",
            "!**/*.dylib",
            "!**/*.dll",
            "!**/*.pch",
            "!**/*.gch",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "CMakeLists.txt",
            "Makefile",
            "meson.build",
            "configure.ac",
            "compile_commands.json",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".c", ".h"]
    }
}

#[derive(Debug, Default)]
pub(super) struct CAnalysis {
    includes: Mutex<ArenaMap<FileId, Vec<String>>>,
}

impl LanguageAnalysis for CAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut includes = Vec::new();

        for &node in nodes {
            dependencies::extract(node, source, &mut includes);
        }

        self.includes.lock().unwrap().insert(file, includes);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let includes = self.includes.lock().unwrap();

        resolve::resolve(index, repository, &includes)
    }
}
