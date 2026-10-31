//! JavaScript outlines, local workspace packages, and static module resolution.

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
pub mod manifest;
pub mod resolve;

/// JavaScript grammar and static local import analysis.
#[derive(Debug)]
pub struct JavaScript;

impl Language for JavaScript {
    fn id(&self) -> &'static str {
        "javascript"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_javascript::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        concat!(
            include_str!("../../queries/javascript.scm"),
            "\n",
            include_str!("../../queries/javascript_fields.scm"),
            "\n",
            include_str!("../../queries/jsx.scm"),
        )
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(JavaScriptAnalysis::default())
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
            "!**/node_modules/**",
            "!**/package-lock.json",
            "!**/npm-shrinkwrap.json",
            "!**/yarn.lock",
            "!**/pnpm-lock.yaml",
            "!**/bun.lock",
            "!**/bun.lockb",
            "!**/*.tsbuildinfo",
            "!**/.next/**",
            "!**/.nuxt/**",
            "!**/.svelte-kit/**",
            "!**/.turbo/**",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["package.json", "pnpm-workspace.yaml"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "package.json",
            "pnpm-workspace.yaml",
            "tsconfig.json",
            "jsconfig.json",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".js", ".jsx", ".mjs", ".cjs"]
    }
}

#[derive(Debug, Default)]
pub(super) struct JavaScriptAnalysis {
    imports: Mutex<ArenaMap<FileId, Vec<dependencies::Import>>>,
}

impl LanguageAnalysis for JavaScriptAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut imports = Vec::new();

        for &node in nodes {
            dependencies::extract(node, source, &mut imports);
        }

        self.imports.lock().unwrap().insert(file, imports);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let imports = self.imports.lock().unwrap();

        resolve::resolve(index, repository, &imports)
    }
}
