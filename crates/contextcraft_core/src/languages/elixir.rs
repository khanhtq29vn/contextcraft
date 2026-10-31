//! Elixir outlines, literal Mix dependencies, and local module references.
//!
//! Resolves literal path and umbrella dependencies, lexical aliases, module
//! directives, and remote module calls. Mix code and macros are not executed;
//! computed project settings and dynamically generated modules are not resolved.

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

/// Elixir grammar for `.ex` sources and `.exs` scripts.
#[derive(Debug)]
pub struct Elixir;

impl Language for Elixir {
    fn id(&self) -> &'static str {
        "elixir"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_elixir::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/elixir.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(
            dependencies::extract,
            resolve,
        ))
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
        &["!**/.elixir_ls/**"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["mix.exs"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["mix.exs", "mix.lock", ".formatter.exs"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".ex", ".exs"]
    }
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, local::References>,
) -> Vec<(FileId, FileId)> {
    local::resolve_symbols(index, repository, references)
}
