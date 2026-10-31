//! PostgreSQL 18 schema and routine outlines using tree-sitter-postgres.
//!
//! Retains schema names, column types, constraints, view definitions, and function
//! signatures for the grammar's supported DDL subset. Routine bodies and bulk DML
//! values are omitted from compact tiers. Unsupported or malformed syntax gets an
//! outline placeholder rather than recovery fragments; FULL preserves all source.
//! No database execution, dialect guessing, or cross-file schema binding is performed.

use tree_sitter as ts;

use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::Analysis;

/// Sql structural outlines.
#[derive(Debug)]
pub struct Sql;

impl Language for Sql {
    fn id(&self) -> &'static str {
        "sql"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_postgres::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/sql.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(())
    }

    fn allow_partial_analysis(&self) -> bool {
        // Recovery could promote statements from an unparsed routine body into its outline.
        false
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        let outline = render_outline(source, analysis, false);
        if outline.trim().is_empty() {
            "-- SQL outline unavailable; use FULL for source.".into()
        } else {
            outline
        }
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        let outline = render_outline(source, analysis, true);
        if outline.trim().is_empty() {
            "-- SQL outline unavailable; use FULL for source.".into()
        } else {
            outline
        }
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
        &[".sql"]
    }
}
