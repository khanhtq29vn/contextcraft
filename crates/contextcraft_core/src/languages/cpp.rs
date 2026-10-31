//! C++ parsing with shared C include resolution.

use tree_sitter as ts;

use super::c::{C, CAnalysis};
use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::package::PackageResolution;

/// C++ grammar and shared C quoted-include analysis.
#[derive(Debug)]
pub struct Cpp;

impl Language for Cpp {
    fn id(&self) -> &'static str {
        "cpp"
    }

    fn package_language(&self) -> &'static str {
        "c"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_cpp::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        concat!(
            include_str!("../../queries/c.scm"),
            "\n",
            include_str!("../../queries/cpp.scm"),
        )
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
        C.ignore_patterns()
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        C.package_metadata_files()
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[
            ".cpp", ".cc", ".cxx", ".c++", ".C", ".hpp", ".hh", ".hxx", ".h++", ".H", ".ipp",
            ".tpp", ".inl",
        ]
    }
}
