//! Vue single-file components with embedded script/style outlines and local imports.
//!
//! Supports JavaScript, TypeScript, TSX, CSS, and SCSS blocks, including script
//! setup and compiler-macro contracts. Components share npm/pnpm ownership and
//! the existing static JavaScript resolver. Template preprocessors, auto-imports,
//! and bundler-specific aliases or query modifiers are not inferred or executed.

use tree_sitter as ts;

use super::{Language, LanguageAnalysis, component, javascript::JavaScript, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Analysis;

/// Vue grammar for `.vue` single-file components.
#[derive(Debug)]
pub struct Vue;

impl Language for Vue {
    fn id(&self) -> &'static str {
        "vue"
    }

    fn package_language(&self) -> &'static str {
        "javascript"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_vue_next::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/vue.scm")
    }

    fn query(&self) -> Result<ts::Query, Error> {
        component::query(self, true)
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(component::ComponentAnalysis::default())
    }

    fn supplement_analysis(
        &self,
        file: FileId,
        root: ts::Node<'_>,
        source: &[u8],
        analysis: &mut Analysis,
    ) {
        component::supplement(file, root, source, analysis, true);
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
        JavaScript.ignore_patterns()
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        JavaScript.package_metadata_files()
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".vue"]
    }
}
