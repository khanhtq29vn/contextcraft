//! Zig declaration outlines and literal file dependencies.
//!
//! Resolves relative `.zig` imports and embedded files within the repository,
//! including binary embeds. Named modules, escaped or computed paths, Zig package
//! manifests, and build-script module wiring are not resolved. Build scripts and
//! compile-time code are never executed; nested `build.zig` files define package
//! boundaries, not inferred workspace membership.

use std::collections::HashMap;
use std::path::Path;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};

/// Zig grammar for `.zig` sources, including `build.zig`.
#[derive(Debug)]
pub struct Zig;

impl Language for Zig {
    fn id(&self) -> &'static str {
        "zig"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_zig::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/zig.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn supplement_analysis(
        &self,
        _file: FileId,
        root: ts::Node<'_>,
        source: &[u8],
        analysis: &mut Analysis,
    ) {
        local::visit(root, |node| {
            if !matches!(
                node.kind(),
                "function_declaration"
                    | "test_declaration"
                    | "variable_declaration"
                    | "container_field"
                    | "using_namespace_declaration"
            ) {
                return;
            }
            let mut parent = node.parent();
            while let Some(ancestor) = parent {
                if ancestor.kind() == "block" {
                    return;
                }
                parent = ancestor.parent();
            }

            let mut cursor = node.walk();
            let end = match node.kind() {
                "function_declaration" => node
                    .child_by_field_name("body")
                    .map_or(node.end_byte(), |body| body.start_byte()),
                "test_declaration" => node
                    .named_children(&mut cursor)
                    .find(|child| child.kind() == "block")
                    .map_or(node.end_byte(), |body| body.start_byte()),
                "variable_declaration" => {
                    let mut children = node.children(&mut cursor);
                    let Some(equals) = children.find(|child| child.kind() == "=") else {
                        let range = node.byte_range();
                        analysis.sigs.push(range.clone());
                        analysis.skel.push(range);
                        return;
                    };
                    let Some(value) =
                        children.find(|child| child.is_named() && child.kind() != "comment")
                    else {
                        return;
                    };
                    if builtin(value, source).is_some_and(|(name, _)| name == "@import") {
                        analysis.imports.push(node.byte_range());
                        return;
                    }
                    if matches!(
                        value.kind(),
                        "struct_declaration"
                            | "enum_declaration"
                            | "union_declaration"
                            | "opaque_declaration"
                    ) {
                        let mut cursor = value.walk();
                        value
                            .children(&mut cursor)
                            .find(|child| child.kind() == "{")
                            .map_or(equals.start_byte(), |body| body.start_byte())
                    } else if simple_value(value, source) {
                        node.end_byte()
                    } else {
                        equals.start_byte()
                    }
                }
                "container_field" => node
                    .children(&mut cursor)
                    .find(|child| child.kind() == "=")
                    .map_or(node.end_byte(), |equals| equals.start_byte()),
                _ => node.end_byte(),
            };
            let header = node.start_byte()..end;
            analysis.sigs.push(header.clone());
            analysis.skel.push(header);
        });
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
        &["!**/.zig-cache/**", "!**/zig-cache/**", "!**/zig-out/**"]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["build.zig"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &["build.zig", "build.zig.zon"]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".zig"]
    }
}

fn simple_value(node: ts::Node<'_>, source: &[u8]) -> bool {
    let mut pending = vec![node];
    while let Some(node) = pending.pop() {
        if builtin(node, source).is_some_and(|(name, _)| name == "@import") {
            continue;
        }
        if !matches!(
            node.kind(),
            "identifier"
                | "builtin_type"
                | "field_expression"
                | "pointer_type"
                | "slice_type"
                | "array_type"
                | "nullable_type"
                | "error_union_type"
                | "error_type"
                | "error_set_declaration"
                | "function_signature"
                | "parameters"
                | "parameter"
                | "integer"
                | "float"
                | "boolean"
                | "comment"
        ) {
            return false;
        }
        let mut cursor = node.walk();
        pending.extend(node.named_children(&mut cursor));
    }
    true
}

fn builtin<'a>(node: ts::Node<'_>, source: &'a [u8]) -> Option<(&'a str, &'a str)> {
    if node.kind() != "builtin_function" || node.has_error() {
        return None;
    }
    let mut cursor = node.walk();
    let name = node
        .named_children(&mut cursor)
        .find(|child| child.kind() == "builtin_identifier")?;
    let name = local::text(name, source);
    if !matches!(name, "@import" | "@embedFile") {
        return None;
    }
    let mut cursor = node.walk();
    let arguments = node
        .named_children(&mut cursor)
        .find(|child| child.kind() == "arguments")?;
    let mut cursor = arguments.walk();
    let mut values = arguments
        .named_children(&mut cursor)
        .filter(|child| child.kind() != "comment");
    let value = values.next()?;
    if value.kind() != "string" || values.next().is_some() {
        return None;
    }
    let path = local::text(value, source)
        .strip_prefix('"')?
        .strip_suffix('"')?;
    (!path.is_empty() && !path.contains(['\\', '\0', '\n', '\r'])).then_some((name, path))
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> local::References {
    let mut references = local::References::default();
    for &node in nodes {
        if let Some((name, path)) = builtin(node, source)
            && !Path::new(path).is_absolute()
            && (name == "@embedFile" || path.ends_with(".zig"))
        {
            references.imports.push((name.into(), path.into()));
        }
    }
    references
}

fn resolve(
    index: &Index,
    _repository: &Repository,
    references: &ArenaMap<FileId, local::References>,
) -> Vec<(FileId, FileId)> {
    // Embeds may be binary or oversized, so target all indexed files, not just readable sources.
    let files: HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        let directory = index.files[file].path.parent().unwrap();
        for (_, path) in &references.imports {
            if let Some(target) = local::find(index, &files, &directory.join(path)) {
                edges.push((file, target));
            }
        }
    }
    local::finish(edges)
}
