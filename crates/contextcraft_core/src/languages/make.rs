//! Make outlines, literal includes, and source/target prerequisites.
//!
//! Conventional Makefiles use their containing directory as the invocation
//! directory; imported fragments inherit it. Standalone fragments use the
//! repository root. Literal file-local variable assignments are propagated until
//! an include invalidates their bindings. Recipes, computed variables, implicit
//! pattern rules, and VPATH searches are not executed or inferred.

use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::Analysis;
use crate::repo::Repository;
use la_arena::ArenaMap;

/// Make structural outlines and static local dependencies.
#[derive(Debug)]
pub struct Make;

impl Language for Make {
    fn id(&self) -> &'static str {
        "make"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_make::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/make.scm")
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

    fn matches_filename(&self, name: &str) -> bool {
        matches!(
            name,
            "Makefile" | "makefile" | "GNUmakefile" | "Makefile.am" | "Makefile.in"
        )
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".mk", ".mak", ".make"]
    }
}

fn words(
    node: ts::Node<'_>,
    source: &[u8],
    variables: &std::collections::HashMap<String, String>,
) -> Vec<String> {
    let mut value = text(node, source).to_owned();
    for _ in 0..32 {
        let Some(start) = value.find('$') else { break };
        let tail = &value[start + 1..];
        let (open, close) = if tail.starts_with('(') {
            ('(', ')')
        } else if tail.starts_with('{') {
            ('{', '}')
        } else {
            return Vec::new();
        };
        let Some(end) = tail.find(close) else {
            return Vec::new();
        };
        let name = tail[open.len_utf8()..end].to_owned();
        let Some(replacement) = variables.get(&name) else {
            return Vec::new();
        };
        if value.len() + replacement.len() > 1_048_576 {
            return Vec::new();
        }
        value.replace_range(start..start + end + 2, replacement);
    }
    value
        .split_whitespace()
        .filter(|value| !value.contains(['$', '\\', '%', '\0']))
        .map(str::to_owned)
        .collect()
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let mut variables = std::collections::HashMap::<String, String>::new();
    for &node in nodes {
        if node.kind() == "variable_assignment" {
            let Some(name) = node.child_by_field_name("name") else {
                continue;
            };
            let name = text(name, source);
            let raw = node
                .child_by_field_name("value")
                .map(|node| text(node, source))
                .unwrap_or("");
            let operator = node
                .child_by_field_name("operator")
                .map(|node| text(node, source))
                .unwrap_or("");
            let top_level = node.parent().is_some_and(|node| node.kind() == "makefile");
            if !top_level
                || raw.contains(['$', '\\', '\n', '\r'])
                || !matches!(operator, "=" | ":=" | "::=" | "+=")
            {
                variables.remove(name);
            } else if operator == "+=" {
                if let Some(value) = variables.get_mut(name) {
                    value.push(' ');
                    value.push_str(raw);
                }
            } else {
                variables.insert(name.to_owned(), raw.to_owned());
            }
            continue;
        }
        if node.kind() == "include_directive" {
            if let Some(names) = node.child_by_field_name("filenames") {
                references.imports.extend(
                    words(names, source, &variables)
                        .into_iter()
                        .map(|path| ("include".into(), path)),
                );
            }
            // Included makefiles can overwrite any binding before subsequent rules.
            variables.clear();
        } else if node.kind() == "rule" {
            let mut cursor = node.walk();
            if let Some(targets) = node
                .named_children(&mut cursor)
                .find(|node| node.kind() == "targets")
            {
                references
                    .exports
                    .extend(words(targets, source, &variables));
            }
            for field in ["normal", "order_only", "prerequisite"] {
                if let Some(prerequisites) = node.child_by_field_name(field) {
                    references.imports.extend(
                        words(prerequisites, source, &variables)
                            .into_iter()
                            .map(|path| ("prerequisite".into(), path)),
                    );
                }
            }
        }
    }
    references
}

/// Includes inherit the invoking makefile's working directory, not the include's directory.
fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::readable_files(index, repository);
    let mut edges = Vec::new();
    let mut reached = std::collections::HashSet::new();
    let entries: Vec<_> = references
        .iter()
        .filter(|(file, _)| {
            index.files[*file]
                .path
                .file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| Make.matches_filename(name))
        })
        .map(|(file, _)| file)
        .collect();
    let entries: Vec<_> = entries
        .iter()
        .copied()
        .map(|file| (file, index.files[file].path.parent().unwrap().to_path_buf()))
        .chain(
            references
                .iter()
                .filter(|(file, _)| !entries.contains(file))
                .map(|(file, _)| (file, std::path::PathBuf::new())),
        )
        .collect();
    for (entry, directory) in entries {
        if reached.contains(&entry) {
            continue;
        }
        let mut pending = vec![entry];
        let mut scope = std::collections::HashSet::new();
        while let Some(file) = pending.pop() {
            if !scope.insert(file) {
                continue;
            }
            reached.insert(file);
            let Some(references) = references.get(file) else {
                continue;
            };
            for (kind, path) in &references.imports {
                if kind != "include" {
                    continue;
                }
                let targets: Vec<_> = if path.contains(['*', '?', '[']) {
                    local::path_glob(&directory, path)
                        .into_iter()
                        .flat_map(|pattern| {
                            files
                                .iter()
                                .filter(move |(path, _)| pattern.is_match(path))
                                .map(|(_, &file)| file)
                        })
                        .collect()
                } else {
                    local::find(index, &files, &directory.join(path))
                        .into_iter()
                        .collect()
                };
                for target in targets {
                    edges.push((file, target));
                    pending.push(target);
                }
            }
        }
        let mut exports = std::collections::HashMap::<_, Vec<_>>::new();
        for &file in &scope {
            if let Some(references) = references.get(file) {
                for name in &references.exports {
                    exports.entry(name.as_str()).or_default().push(file);
                }
            }
        }
        for &file in &scope {
            let Some(references) = references.get(file) else {
                continue;
            };
            for (kind, path) in &references.imports {
                if kind != "prerequisite" {
                    continue;
                }
                if let Some(target) = local::find(index, &files, &directory.join(path)) {
                    edges.push((file, target));
                } else if let Some(targets) = exports.get(path.as_str())
                    && let [target] = targets.as_slice()
                {
                    edges.push((file, *target));
                }
            }
        }
    }
    local::finish(edges)
}
