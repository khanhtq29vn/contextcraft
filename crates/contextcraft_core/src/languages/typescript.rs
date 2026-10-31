//! TypeScript and TSX parsing with JavaScript package ownership.

use tree_sitter as ts;

use super::javascript::{JavaScript, JavaScriptAnalysis};
use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::package::PackageResolution;

/// TypeScript grammar configuration. Defaults to TypeScript without JSX.
#[derive(Debug, Default)]
pub struct TypeScript {
    tsx: bool,
}

impl TypeScript {
    /// Creates a configuration using the TSX grammar to parse TypeScript with JSX.
    pub fn tsx() -> Self {
        Self { tsx: true }
    }
}

impl Language for TypeScript {
    fn id(&self) -> &'static str {
        if self.tsx { "tsx" } else { "typescript" }
    }

    fn package_language(&self) -> &'static str {
        "javascript"
    }

    fn grammar(&self) -> ts::Language {
        if self.tsx {
            tree_sitter_typescript::LANGUAGE_TSX.into()
        } else {
            tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
        }
    }

    fn source_query(&self) -> &'static str {
        if self.tsx {
            concat!(
                include_str!("../../queries/javascript.scm"),
                "\n",
                include_str!("../../queries/typescript.scm"),
                "\n",
                include_str!("../../queries/jsx.scm"),
            )
        } else {
            concat!(
                include_str!("../../queries/javascript.scm"),
                "\n",
                include_str!("../../queries/typescript.scm"),
            )
        }
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(JavaScriptAnalysis::default())
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
        if self.tsx {
            &[".tsx"]
        } else {
            &[".ts", ".mts", ".cts"]
        }
    }
}
