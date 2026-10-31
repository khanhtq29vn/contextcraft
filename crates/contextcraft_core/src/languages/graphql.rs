//! GraphQL schema/operation outlines and explicitly imported local fragments.
//!
//! GraphQL-tools-style `# import` comments establish cross-file visibility.
//! Literal JSON/YAML GraphQL project document globs also establish visibility.
//! Executable configuration and fragments in unrelated projects are not inferred.

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

/// Graphql structural outlines and static local dependencies.
#[derive(Debug)]
pub struct Graphql;

impl Language for Graphql {
    fn id(&self) -> &'static str {
        "graphql"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_graphql::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/graphql.scm")
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
        &[
            ".graphqlrc",
            ".graphqlrc.json",
            ".graphqlrc.yaml",
            ".graphqlrc.yml",
            "graphql.config.json",
            "graphql.config.yaml",
            "graphql.config.yml",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".graphql", ".gql", ".graphqls"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "comment" {
            let comment = text(node, source).trim_start_matches('#').trim();
            let Some(import) = comment
                .strip_prefix("import")
                .filter(|value| value.starts_with(char::is_whitespace))
            else {
                continue;
            };
            let import = import.trim();
            let path = if import.starts_with(['\'', '"']) {
                import
            } else {
                import
                    .split_once(" from ")
                    .map(|(_, path)| path.trim())
                    .unwrap_or("")
            };
            if path.len() >= 2
                && path.starts_with(['\'', '"'])
                && path.as_bytes().first() == path.as_bytes().last()
            {
                let path = &path[1..path.len() - 1];
                if !path.contains(['\n', '\r', '\0', '\\']) && !path.contains("://") {
                    references.imports.push(("import".into(), path.into()));
                }
            }
        } else {
            let mut cursor = node.walk();
            if let Some(name) = node
                .named_children(&mut cursor)
                .find(|node| node.kind() == "fragment_name")
            {
                let name = text(name, source).to_owned();
                if node.kind() == "fragment_definition" {
                    references.exports.push(name);
                } else {
                    references.imports.push(("spread".into(), name));
                }
            }
        }
    }
    references
}

/// Cross-file fragment lookup is restricted to explicit GraphQL-tools-style imports.
fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::readable_files(index, repository);
    let mut edges = Vec::new();
    let mut imports = std::collections::HashMap::<_, Vec<_>>::new();
    let mut definitions = std::collections::HashMap::<_, Vec<_>>::new();
    for (file, references) in references.iter() {
        for name in &references.exports {
            definitions.entry(name.as_str()).or_default().push(file);
        }
        for (kind, path) in &references.imports {
            if kind == "import"
                && let Some(target) = local::find(
                    index,
                    &files,
                    &index.files[file].path.parent().unwrap().join(path),
                )
            {
                edges.push((file, target));
                imports.entry(file).or_default().push(target);
            }
        }
    }
    let configured = document_sets(index, repository);
    for (file, references) in references.iter() {
        let mut visible = std::collections::HashSet::from([file]);
        let mut pending = vec![file];
        while let Some(file) = pending.pop() {
            for &target in imports.get(&file).into_iter().flatten() {
                if visible.insert(target) {
                    pending.push(target);
                }
            }
        }
        for group in configured.iter().filter(|group| group.contains(&file)) {
            visible.extend(group);
        }
        for (kind, name) in &references.imports {
            if kind != "spread" {
                continue;
            }
            let mut targets: Vec<_> = definitions
                .get(name.as_str())
                .into_iter()
                .flatten()
                .filter(|file| visible.contains(file))
                .copied()
                .collect();
            targets.sort_unstable();
            targets.dedup();
            if let [target] = targets.as_slice() {
                edges.push((file, *target));
            }
        }
    }
    local::finish(edges)
}

/// Executable GraphQL configuration files are deliberately not loaded.
fn document_sets(index: &Index, repository: &Repository) -> Vec<std::collections::HashSet<FileId>> {
    use serde_json::Value;
    let mut groups = Vec::new();
    for (id, file) in index.files.iter() {
        if !file.path.file_name().is_some_and(|name| {
            matches!(
                name.to_str(),
                Some(
                    ".graphqlrc"
                        | ".graphqlrc.json"
                        | ".graphqlrc.yaml"
                        | ".graphqlrc.yml"
                        | "graphql.config.json"
                        | "graphql.config.yaml"
                        | "graphql.config.yml"
                )
            )
        }) {
            continue;
        }
        let Some(source) = repository.sources.get(id) else {
            continue;
        };
        let Ok(raw) = std::str::from_utf8(&source.bytes) else {
            continue;
        };
        let Some(document) = serde_json::from_str::<Value>(raw)
            .ok()
            .or_else(|| local::yaml_config(raw))
        else {
            continue;
        };
        let projects: Vec<_> = document
            .get("projects")
            .and_then(Value::as_object)
            .map_or_else(|| vec![&document], |projects| projects.values().collect());
        for project in projects {
            let patterns: Vec<_> = project
                .get("documents")
                .into_iter()
                .flat_map(|value| {
                    value
                        .as_array()
                        .map_or_else(|| vec![value], |values| values.iter().collect())
                })
                .filter_map(Value::as_str)
                .collect();
            let globs: Vec<_> = patterns
                .iter()
                .filter_map(|pattern| {
                    local::path_glob(
                        file.path.parent().unwrap(),
                        pattern.strip_prefix('!').unwrap_or(pattern),
                    )
                    .map(|glob| (pattern.starts_with('!'), glob))
                })
                .collect();
            let group = index
                .files
                .iter()
                .filter(|(id, file)| {
                    file.language == Some("graphql")
                        && repository.sources.get(*id).is_some()
                        && globs
                            .iter()
                            .any(|(negative, glob)| !negative && glob.is_match(&file.path))
                        && !globs
                            .iter()
                            .any(|(negative, glob)| *negative && glob.is_match(&file.path))
                })
                .map(|(id, _)| id)
                .collect();
            groups.push(group);
        }
    }
    groups
}
