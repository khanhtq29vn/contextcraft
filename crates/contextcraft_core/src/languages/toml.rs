//! TOML table, key, and scalar-value outlines.

use tree_sitter as ts;

use super::{Language, render_outline};
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

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".toml"]
    }
}
