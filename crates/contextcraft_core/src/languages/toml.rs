//! TOML table, key, and scalar-value outlines.

use tree_sitter as ts;

use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::Analysis;

/// TOML table, key, and scalar-value outlines.
#[derive(Debug)]
pub struct Toml;

impl Language for Toml {
    fn id(&self) -> &'static str {
        "toml"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_toml_ng::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/toml.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(())
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
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
        &[".toml"]
    }
}
