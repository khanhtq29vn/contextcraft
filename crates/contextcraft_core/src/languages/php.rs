//! PHP declarations, namespace imports, literal includes, and Composer autoload roots.
//!
//! Dynamic includes, custom autoloaders, and runtime class loading are not evaluated.

use std::collections::HashMap;
use std::path::Path;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};

pub mod manifest;

/// PHP grammar, including PHP embedded in HTML templates.
#[derive(Debug)]
pub struct Php;

impl Language for Php {
    fn id(&self) -> &'static str {
        "php"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_php::LANGUAGE_PHP.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/php.scm")
    }

    fn interpreters(&self) -> &'static [&'static str] {
        &["php"]
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        manifest::discover(index, config)
    }

    fn supplement_analysis(
        &self,
        _file: FileId,
        root: ts::Node<'_>,
        _source: &[u8],
        analysis: &mut Analysis,
    ) {
        local::visit(root, |node| {
            if !matches!(node.kind(), "property_declaration" | "const_declaration") {
                return;
            }
            let mut cursor = node.walk();
            let mut first = true;
            for element in node
                .named_children(&mut cursor)
                .filter(|node| matches!(node.kind(), "property_element" | "const_element"))
            {
                if let Some(name) = element
                    .child_by_field_name("name")
                    .or_else(|| element.named_child(0))
                {
                    let range = if first {
                        node.start_byte()..name.end_byte()
                    } else {
                        name.byte_range()
                    };
                    analysis.sigs.push(range.clone());
                    analysis.skel.push(range);
                    first = false;
                }
            }
        });
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/vendor/**",
            "!**/composer.lock",
            "!**/.phpunit.cache/**",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["composer.json"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["composer.json", "composer.lock"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".php", ".phtml", ".inc"]
    }
}

fn context<'tree>(node: ts::Node<'tree>, source: &[u8]) -> (usize, String) {
    let mut parent = Some(node);
    while let Some(ancestor) = parent {
        if ancestor.kind() == "namespace_definition" {
            return (
                ancestor.start_byte(),
                ancestor
                    .child_by_field_name("name")
                    .map_or("", |name| text(name, source))
                    .into(),
            );
        }
        if ancestor.kind() == "program" {
            let mut cursor = ancestor.walk();
            if let Some(namespace) = ancestor
                .named_children(&mut cursor)
                .filter(|sibling| {
                    sibling.kind() == "namespace_definition"
                        && sibling.child_by_field_name("body").is_none()
                        && sibling.end_byte() <= node.start_byte()
                })
                .last()
            {
                return (
                    namespace.start_byte(),
                    namespace
                        .child_by_field_name("name")
                        .map_or("", |name| text(name, source))
                        .into(),
                );
            }
        }
        parent = ancestor.parent();
    }
    (0, String::new())
}

fn imports(node: ts::Node<'_>, source: &[u8]) -> Vec<(String, String)> {
    if node
        .child_by_field_name("type")
        .is_some_and(|kind| text(kind, source) == "const")
    {
        return Vec::new();
    }
    let mut cursor = node.walk();
    let prefix = node
        .named_children(&mut cursor)
        .find(|node| node.kind() == "namespace_name")
        .map_or("", |node| text(node, source));
    let mut imports = Vec::new();
    local::visit(node, |clause| {
        if clause.kind() != "namespace_use_clause"
            || clause
                .child_by_field_name("type")
                .is_some_and(|kind| text(kind, source) == "const")
        {
            return;
        }
        let alias_node = clause.child_by_field_name("alias");
        let mut cursor = clause.walk();
        if let Some(name) = clause.named_children(&mut cursor).find(|node| {
            Some(*node) != alias_node && matches!(node.kind(), "name" | "qualified_name")
        }) {
            let name = text(name, source).trim_start_matches('\\');
            let value = if prefix.is_empty() {
                name.into()
            } else {
                format!("{}\\{name}", prefix.trim_matches('\\'))
            };
            let alias = alias_node.map_or_else(
                || name.rsplit('\\').next().unwrap().to_owned(),
                |node| text(node, source).into(),
            );
            imports.push((alias.to_lowercase(), value));
        }
    });
    imports
}

fn include_path(node: ts::Node<'_>, source: &[u8]) -> Option<(bool, String)> {
    if text(node, source) == "__DIR__" {
        return Some((true, String::new()));
    }
    if matches!(node.kind(), "string" | "encapsed_string") {
        let value = text(node, source);
        let quote = value.as_bytes().first()?;
        if !matches!(quote, b'\'' | b'"') || value.len() < 2 || value.as_bytes().last()? != quote {
            return None;
        }
        let value = &value[1..value.len() - 1];
        if value.contains(['\\', '\0', '\n', '\r']) || *quote == b'"' && value.contains('$') {
            return None;
        }
        return Some((false, value.into()));
    }
    if node.kind() == "parenthesized_expression" {
        return include_path(node.named_child(0)?, source);
    }
    if node.kind() == "binary_expression"
        && text(node.child_by_field_name("operator")?, source) == "."
    {
        let (anchored, left) = include_path(node.child_by_field_name("left")?, source)?;
        let (right_anchored, right) = include_path(node.child_by_field_name("right")?, source)?;
        if !right_anchored {
            return Some((anchored, left + &right));
        }
    }
    None
}

fn qualified(value: &str, namespace: &str, aliases: Option<&HashMap<String, String>>) -> String {
    if value.starts_with('\\') {
        return value.trim_start_matches('\\').to_lowercase();
    }
    let value = if let Some(value) = value.strip_prefix("namespace\\") {
        return format!("{namespace}\\{value}")
            .trim_start_matches('\\')
            .to_lowercase();
    } else {
        value
    };
    let (first, suffix) = value
        .split_once('\\')
        .map_or((value, ""), |(first, suffix)| (first, suffix));
    if let Some(import) = aliases.and_then(|aliases| aliases.get(&first.to_lowercase())) {
        return if suffix.is_empty() {
            import.to_lowercase()
        } else {
            format!("{import}\\{suffix}").to_lowercase()
        };
    }
    format!("{namespace}\\{value}")
        .trim_start_matches('\\')
        .to_lowercase()
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let Some(&root) = nodes.first() else {
        return references;
    };
    let mut aliases: HashMap<usize, HashMap<String, String>> = HashMap::new();
    local::visit(root, |node| {
        if node.kind() == "namespace_use_declaration" {
            let (scope, _) = context(node, source);
            for (alias, name) in imports(node, source) {
                references
                    .imports
                    .push(("type".into(), name.to_lowercase()));
                aliases.entry(scope).or_default().insert(alias, name);
            }
        }
    });
    local::visit(root, |node| {
        let (scope, namespace) = context(node, source);
        match node.kind() {
            "class_declaration"
            | "interface_declaration"
            | "trait_declaration"
            | "enum_declaration"
            | "function_definition" => {
                let Some(name) = node.child_by_field_name("name") else {
                    return;
                };
                let mut parent = node.parent();
                while let Some(ancestor) = parent {
                    if matches!(
                        ancestor.kind(),
                        "function_definition"
                            | "method_declaration"
                            | "anonymous_function"
                            | "arrow_function"
                    ) {
                        return;
                    }
                    parent = ancestor.parent();
                }
                references.exports.push(
                    format!("{namespace}\\{}", text(name, source))
                        .trim_start_matches('\\')
                        .to_lowercase(),
                );
            }
            "include_expression"
            | "include_once_expression"
            | "require_expression"
            | "require_once_expression" => {
                if let Some((anchored, path)) = node
                    .named_child(0)
                    .and_then(|expression| include_path(expression, source))
                {
                    references
                        .imports
                        .push((if anchored { "dir" } else { "file" }.into(), path));
                }
            }
            "name" | "qualified_name" | "relative_name" => {
                let Some(parent) = node.parent() else {
                    return;
                };
                if matches!(
                    parent.kind(),
                    "named_type"
                        | "base_clause"
                        | "class_interface_clause"
                        | "object_creation_expression"
                        | "use_declaration"
                        | "attribute"
                ) || parent.child_by_field_name("scope") == Some(node)
                    || parent.kind() == "function_call_expression"
                        && parent.child_by_field_name("function") == Some(node)
                {
                    references.imports.push((
                        "type".into(),
                        qualified(text(node, source), &namespace, aliases.get(&scope)),
                    ));
                }
            }
            _ => {}
        }
    });
    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut symbols = references.clone();
    for (file, reference) in symbols.iter_mut() {
        let package = &index.packages[index.files[file].package_id];
        if package.language == Some("php") && !package.targets.contains(&file) {
            reference.exports.clear();
        }
    }
    let mut edges = local::resolve_symbols(index, repository, &symbols);
    let files = local::readable_files(index, repository);
    for (file, reference) in references.iter() {
        let directory = index.files[file].path.parent().unwrap();
        for (kind, path) in &reference.imports {
            let path = if kind == "dir" {
                directory.join(path.trim_start_matches('/'))
            } else if kind == "file" && !Path::new(path).is_absolute() && !path.contains("://") {
                directory.join(path)
            } else {
                continue;
            };
            if let Some(target) = local::find(index, &files, &path) {
                edges.push((file, target));
            }
        }
    }
    local::finish(edges)
}
