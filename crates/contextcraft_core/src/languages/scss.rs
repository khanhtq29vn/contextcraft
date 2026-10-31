//! SCSS outlines and local Sass filesystem imports using the modern SCSS grammar.
//!
//! Resolves `@use`, `@forward`, and legacy `@import` with Sass partial, extension,
//! index, and import-only precedence. Ambiguous matches, interpolation, built-ins,
//! configured load paths, and custom package importers are not inferred.

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

/// Scss structural outlines and static local imports.
#[derive(Debug)]
pub struct Scss;

impl Language for Scss {
    fn id(&self) -> &'static str {
        "scss"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_scss::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/scss.scm")
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

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".scss"]
    }
}

pub(super) fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "call_expression" {
            if let Some(arguments) = node.named_child(1)
                && let Some(raw) = text(arguments, source)
                    .strip_prefix('(')
                    .and_then(|raw| raw.strip_suffix(')'))
                && let Some(path) = super::css::import_path(raw)
            {
                references.imports.push(("css".into(), path));
            }
            continue;
        }
        if node.has_error() {
            continue;
        }

        let legacy = node.kind() == "import_statement";
        let mut cursor = node.walk();
        let media = legacy
            && node
                .named_children(&mut cursor)
                .any(|node| node.kind().ends_with("_query"));
        for (path, url) in super::css::import_paths(node, source, legacy) {
            let kind = if legacy && (url || media || path.ends_with(".css")) {
                "css"
            } else if legacy {
                "import"
            } else {
                "module"
            };
            references.imports.push((kind.into(), path));
        }
    }
    references
}

fn partials(path: std::path::PathBuf) -> Vec<std::path::PathBuf> {
    let mut paths = vec![path.clone()];
    if let Some(name) = path.file_name() {
        paths.push(path.with_file_name(format!("_{}", name.to_string_lossy())));
    }
    paths
}

fn with_extensions(path: &std::path::Path) -> Vec<Vec<std::path::PathBuf>> {
    let append = |extension: &str| {
        let mut name = path.as_os_str().to_os_string();
        name.push(extension);
        partials(name.into())
    };
    vec![
        append(".scss").into_iter().chain(append(".sass")).collect(),
        append(".css"),
    ]
}

/// Follows Sass's filesystem precedence without guessing configured load paths.
fn module_file(
    index: &Index,
    files: &std::collections::HashMap<&std::path::Path, FileId>,
    path: &std::path::Path,
    legacy: bool,
) -> Option<FileId> {
    let mut groups = Vec::new();
    let extension = path.extension().and_then(|extension| extension.to_str());
    if let Some(extension @ ("scss" | "sass" | "css")) = extension {
        if legacy {
            let stem = path.file_stem()?.to_string_lossy();
            groups.push(partials(
                path.with_file_name(format!("{stem}.import.{extension}")),
            ));
        }
        groups.push(partials(path.to_path_buf()));
    } else {
        if legacy {
            let mut name = path.as_os_str().to_os_string();
            name.push(".import");
            groups.extend(with_extensions(std::path::Path::new(&name)));
        }
        groups.extend(with_extensions(path));
        if legacy {
            groups.extend(with_extensions(&path.join("index.import")));
        }
        groups.extend(with_extensions(&path.join("index")));
    }
    for group in groups {
        let mut targets: Vec<_> = group
            .iter()
            .filter_map(|path| local::find(index, files, path))
            .collect();
        targets.sort_unstable();
        targets.dedup();
        match targets.as_slice() {
            [] => {}
            [target] => return Some(*target),
            _ => return None,
        }
    }
    None
}

pub(super) fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::readable_files(index, repository);
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        for (kind, path) in &references.imports {
            let path = index.files[file].path.parent().unwrap().join(path);
            let target = if kind == "css" {
                local::find(index, &files, &path)
            } else {
                module_file(index, &files, &path, kind == "import")
            };
            if let Some(target) = target {
                edges.push((file, target));
            }
        }
    }
    local::finish(edges)
}
