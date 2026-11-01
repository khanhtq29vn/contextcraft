//! C++ parsing with shared C include resolution.

use tree_sitter as ts;

use super::c::{C, CAnalysis};
use super::{Language, LanguageAnalysis};

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

    fn content_evidence(&self, source: &[u8]) -> super::detect::Evidence {
        use super::detect::Evidence;

        let mut parser = ts::Parser::new();
        if parser.set_language(&self.grammar()).is_err() {
            return Evidence::Unknown;
        }
        let Some(tree) = parser.parse(source, None) else {
            return Evidence::Unknown;
        };

        // Recovered trees can still contain positive evidence outside syntax errors.
        let mut cursor = tree.walk();
        loop {
            let node = cursor.node();
            if !node.is_error()
                && !node.is_missing()
                && matches!(
                    node.kind(),
                    "class_specifier"
                        | "namespace_definition"
                        | "template_declaration"
                        | "using_declaration"
                        | "alias_declaration"
                        | "access_specifier"
                        | "qualified_identifier"
                        | "reference_declarator"
                        | "abstract_reference_declarator"
                )
            {
                return Evidence::Supports;
            }

            if cursor.goto_first_child() {
                continue;
            }
            while !cursor.goto_next_sibling() {
                if !cursor.goto_parent() {
                    return Evidence::Unknown;
                }
            }
        }
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(CAnalysis::default())
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        C.ignore_patterns()
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        C.package_metadata_files()
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[
            ".cpp", ".cc", ".cxx", ".c++", ".C", ".h", ".hpp", ".hh", ".hxx", ".h++", ".H", ".ipp",
            ".tpp", ".inl",
        ]
    }
}
