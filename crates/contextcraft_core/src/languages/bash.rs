//! Bash `.sh` outlines and literal `source`/`.` dependencies.
//!
//! Source paths are resolved against the repository working directory. Runtime
//! expansions, PATH lookup, extensionless scripts, and shebang detection are not evaluated.

use tree_sitter as ts;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::index::FileId;
use crate::index::Index;
use crate::repo::{Analysis, Repository};
use la_arena::ArenaMap;
use local::{References, text};

/// Bash grammar and local project analysis.
#[derive(Debug)]
pub struct Bash;

impl Language for Bash {
    fn id(&self) -> &'static str {
        "bash"
    }

    fn interpreters(&self) -> &'static [&'static str] {
        &["sh", "bash"]
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_bash::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/bash.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".sh"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();

    for &node in nodes {
        let Some(argument) = node.child_by_field_name("argument") else {
            continue;
        };
        let value = if argument.kind() == "word" {
            let value = text(argument, source);
            (!value.contains(['$', '`', '\\', '*', '?', '['])).then(|| value.to_owned())
        } else {
            let value = local::literal(argument, source);
            value.filter(|value| argument.kind() == "raw_string" || !value.contains(['$', '`']))
        };

        if let Some(value) = value {
            references.imports.push(("source".into(), value));
        }
    }

    references
}

/// Literal source paths are interpreted relative to the repository working directory.
fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::file_lookup(index, repository, "bash");
    let mut edges = Vec::new();

    for (file, references) in references.iter() {
        for (_, path) in &references.imports {
            if let Some(target) = local::find(index, &files, std::path::Path::new(path)) {
                edges.push((file, target));
            }
        }
    }

    local::finish(edges)
}
