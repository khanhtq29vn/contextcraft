//! Svelte component markup, embedded script/style outlines, and local imports.
//!
//! Supports JavaScript/TypeScript scripts, module scripts, Svelte 5 template
//! blocks, and CSS/SCSS styles. Components share npm/pnpm ownership and the static
//! JavaScript resolver. Preprocessors, auto-imports, generated aliases, and bundler
//! query modifiers are not inferred or executed.

use tree_sitter as ts;

use super::{Language, LanguageAnalysis, component, javascript::JavaScript, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Analysis;

/// Svelte grammar for `.svelte` single-file components.
#[derive(Debug)]
pub struct Svelte;

impl Language for Svelte {
    fn id(&self) -> &'static str {
        "svelte"
    }

    fn package_language(&self) -> &'static str {
        "javascript"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_svelte_ng::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/svelte.scm")
    }

    fn query(&self) -> Result<ts::Query, Error> {
        component::query(self, false)
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
        component::supplement(file, root, source, analysis, false);
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
        &[".svelte"]
    }
}
