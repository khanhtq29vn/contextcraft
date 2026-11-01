//! R function outlines, literal source calls, and static local package namespaces.
//!
//! DESCRIPTION and NAMESPACE restrict package visibility and exported symbols.
//! Computed paths, nonstandard evaluation, runtime search paths, and package installation
//! are not evaluated. R Markdown and Quarto documents are not parsed as R source.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::Path;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};

pub mod manifest;

/// R grammar for source files and NAMESPACE declarations.
#[derive(Debug)]
pub struct R;

impl Language for R {
    fn id(&self) -> &'static str {
        "r"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_r::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/r.scm")
    }

    fn interpreters(&self) -> &'static [&'static str] {
        &["Rscript", "R"]
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
        let mut cursor = root.walk();
        for node in root.named_children(&mut cursor) {
            let Some((name, value)) = assignment(node, source) else {
                continue;
            };
            if value.kind() == "function_definition" {
                if let Some(body) = value.child_by_field_name("body") {
                    let range = node.start_byte()..body.start_byte();
                    analysis.sigs.push(range.clone());
                    analysis.skel.push(range);
                    if name.start_byte() > value.end_byte() {
                        let range = value.end_byte()..node.end_byte();
                        analysis.sigs.push(range.clone());
                        analysis.skel.push(range);
                    }
                }
            } else {
                analysis.sigs.push(name.byte_range());
                analysis.skel.push(name.byte_range());
            }
        }
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        manifest::discover(index, config)
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/renv/library/**",
            "!**/renv/staging/**",
            "!**/renv.lock",
            "!**/packrat/lib/**",
            "!**/*.rds",
            "!**/*.RData",
            "!**/*.rda",
            "!**/.Rhistory",
            "!**/.Rproj.user/**",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["DESCRIPTION"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "DESCRIPTION",
            "NAMESPACE",
            "renv.lock",
            ".Rprofile",
            ".Renviron",
        ]
    }

    fn matches_filename(&self, name: &str) -> bool {
        matches!(name, "NAMESPACE" | ".Rprofile" | "Rprofile.site")
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".R", ".r", ".Rscript", ".rscript"]
    }
}

fn name(node: ts::Node<'_>, source: &[u8]) -> Option<String> {
    if node.kind() == "identifier" {
        Some(text(node, source).trim_matches('`').into())
    } else {
        local::literal(node, source)
    }
}

fn assignment<'tree>(
    node: ts::Node<'tree>,
    source: &[u8],
) -> Option<(ts::Node<'tree>, ts::Node<'tree>)> {
    if node.kind() != "binary_operator" {
        return None;
    }
    let left = node.child_by_field_name("lhs")?;
    let right = node.child_by_field_name("rhs")?;
    let (name, value) = match text(node.child_by_field_name("operator")?, source) {
        "<-" | "<<-" | "=" => (left, right),
        "->" | "->>" => (right, left),
        _ => return None,
    };
    matches!(name.kind(), "identifier" | "string").then_some((name, value))
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let Some(&root) = nodes.first() else {
        return references;
    };
    let mut cursor = root.walk();
    for node in root.named_children(&mut cursor) {
        if let Some((target, _)) = assignment(node, source)
            && let Some(name) = name(target, source)
        {
            references.exports.push(name);
        }
    }
    local::visit(root, |node| {
        if node.kind() == "namespace_operator" {
            if let (Some(package), Some(symbol), Some(operator)) = (
                node.child_by_field_name("lhs")
                    .and_then(|node| name(node, source)),
                node.child_by_field_name("rhs")
                    .and_then(|node| name(node, source)),
                node.child_by_field_name("operator"),
            ) {
                references.imports.push((
                    if text(operator, source) == ":::" {
                        "internal"
                    } else {
                        "qualified"
                    }
                    .into(),
                    format!("{package}::{symbol}"),
                ));
            }
            return;
        }
        if node.kind() != "call" {
            return;
        }
        let Some(function) = node.child_by_field_name("function") else {
            return;
        };
        let function = if function.kind() == "namespace_operator"
            && function
                .child_by_field_name("lhs")
                .is_some_and(|node| text(node, source) == "base")
        {
            let Some(function) = function.child_by_field_name("rhs") else {
                return;
            };
            function
        } else {
            function
        };
        if function.kind() != "identifier" {
            return;
        }
        let method = text(function, source).trim_matches('`');
        let Some(arguments) = node.child_by_field_name("arguments") else {
            return;
        };
        let mut cursor = arguments.walk();
        let arguments: Vec<_> = arguments
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "argument")
            .collect();
        let first = arguments
            .iter()
            .find(|argument| argument.child_by_field_name("name").is_none())
            .or_else(|| {
                arguments.iter().find(|argument| {
                    argument
                        .child_by_field_name("name")
                        .is_some_and(|name| matches!(text(name, source), "package" | "file"))
                })
            })
            .and_then(|argument| argument.child_by_field_name("value"));
        match method {
            "source" | "sys.source" => {
                if let Some(path) = first.and_then(|node| local::literal(node, source)) {
                    references.imports.push(("file".into(), path));
                }
            }
            "library" | "require" | "requireNamespace" | "loadNamespace" => {
                let character_only = arguments.iter().any(|argument| {
                    argument
                        .child_by_field_name("name")
                        .is_some_and(|node| text(node, source) == "character.only")
                        && argument
                            .child_by_field_name("value")
                            .is_some_and(|node| !matches!(text(node, source), "FALSE" | "F"))
                });
                if let Some(package) = first.and_then(|node| {
                    if character_only || matches!(method, "requireNamespace" | "loadNamespace") {
                        local::literal(node, source)
                    } else {
                        name(node, source)
                    }
                }) {
                    references.imports.push((
                        if matches!(method, "requireNamespace" | "loadNamespace") {
                            "load"
                        } else {
                            "package"
                        }
                        .into(),
                        package,
                    ));
                }
            }
            "import" | "importFrom" => {
                if let Some(package) = first.and_then(|node| name(node, source)) {
                    if method == "import" {
                        for argument in &arguments {
                            if let Some(package) = argument
                                .child_by_field_name("value")
                                .and_then(|node| name(node, source))
                            {
                                references.imports.push(("package".into(), package));
                            }
                        }
                    } else {
                        for argument in arguments.iter().skip(1) {
                            if let Some(symbol) = argument
                                .child_by_field_name("value")
                                .and_then(|node| name(node, source))
                            {
                                references
                                    .imports
                                    .push(("from".into(), format!("{package}::{symbol}")));
                            }
                        }
                    }
                }
            }
            "export" | "exportPattern" => {
                for argument in &arguments {
                    if let Some(value) = argument
                        .child_by_field_name("value")
                        .and_then(|node| name(node, source))
                    {
                        references.imports.push((
                            if method == "export" {
                                "export"
                            } else {
                                "pattern"
                            }
                            .into(),
                            value,
                        ));
                    }
                }
            }
            _ => references.imports.push(("call".into(), method.into())),
        }
    });
    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut declarations: HashMap<PackageId, BTreeMap<&str, Vec<FileId>>> = HashMap::new();
    let mut namespaces = HashMap::new();
    for (file, reference) in references.iter() {
        let metadata = &index.files[file];
        let package = &index.packages[metadata.package_id];
        if metadata.path == package.root.join("NAMESPACE") {
            namespaces.insert(metadata.package_id, reference);
        }
        if package.language != Some("r") || package.targets.contains(&file) {
            for name in &reference.exports {
                declarations
                    .entry(metadata.package_id)
                    .or_default()
                    .entry(name)
                    .or_default()
                    .push(file);
            }
        }
    }
    let patterns: HashMap<_, Vec<_>> = namespaces
        .iter()
        .map(|(&package, namespace)| {
            (
                package,
                namespace
                    .imports
                    .iter()
                    .filter(|(kind, _)| kind == "pattern")
                    .filter_map(|(_, pattern)| regex::Regex::new(pattern).ok())
                    .collect(),
            )
        })
        .collect();
    let exported = |package: PackageId, name: &str| {
        namespaces.get(&package).is_none_or(|namespace| {
            namespace
                .imports
                .iter()
                .any(|(kind, value)| kind == "export" && value == name)
                || patterns[&package]
                    .iter()
                    .any(|pattern| pattern.is_match(name))
        })
    };
    let mut edges = Vec::new();
    let mut visibility = HashMap::new();
    let files = local::readable_files(index, repository);
    let attached: HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("r"))
        .map(|(id, package)| {
            let names = package
                .manifests
                .iter()
                .filter_map(|path| files.get(path.as_path()))
                .filter_map(|file| std::str::from_utf8(&repository.sources[*file].bytes).ok())
                .flat_map(manifest::attached_packages)
                .collect::<Vec<_>>();
            (id, names)
        })
        .collect();
    for (file, reference) in references.iter() {
        let owner = index.files[file].package_id;
        let visible = visibility
            .entry(owner)
            .or_insert_with(|| local::visible(index, owner));
        let package_target = |name: &str| {
            let candidates: Vec<_> = index
                .packages
                .iter()
                .filter(|(id, package)| {
                    package.language == Some("r")
                        && package.name.as_deref() == Some(name)
                        && (index.packages[owner].language != Some("r") || visible.contains(id))
                })
                .map(|(id, _)| id)
                .collect();
            if let [target] = candidates.as_slice() {
                Some(*target)
            } else {
                None
            }
        };
        let mut imports = reference.imports.clone();
        if let Some(namespace) = namespaces.get(&owner) {
            imports.extend(namespace.imports.clone());
        }
        if let Some(names) = attached.get(&owner) {
            imports.extend(names.iter().map(|name| ("package".into(), name.clone())));
        }
        let loaded: HashSet<_> = imports
            .iter()
            .filter(|(kind, _)| kind == "package")
            .filter_map(|(_, name)| package_target(name))
            .collect();
        for (kind, value) in &imports {
            if kind == "file" {
                if !Path::new(value).is_absolute()
                    && !value.contains("://")
                    && let Some(target) = local::find(index, &files, Path::new(value))
                {
                    edges.push((file, target));
                }
                continue;
            }
            let mut candidates = Vec::new();
            if matches!(kind.as_str(), "qualified" | "internal" | "from") {
                if let Some((package, symbol)) = value.split_once("::")
                    && let Some(package) = package_target(package)
                    && (kind == "internal" || exported(package, symbol))
                    && let Some(targets) = declarations
                        .get(&package)
                        .and_then(|declarations| declarations.get(symbol))
                {
                    candidates.extend(targets.iter().copied());
                }
            } else if kind == "call" {
                if let Some(targets) = declarations
                    .get(&owner)
                    .and_then(|declarations| declarations.get(value.as_str()))
                {
                    candidates.extend(targets.iter().copied());
                } else {
                    for &package in &loaded {
                        if exported(package, value)
                            && let Some(targets) = declarations
                                .get(&package)
                                .and_then(|declarations| declarations.get(value.as_str()))
                        {
                            candidates.extend(targets.iter().copied());
                        }
                    }
                    for (kind, imported) in &imports {
                        if kind == "from"
                            && let Some((package, symbol)) = imported.split_once("::")
                            && symbol == value
                            && let Some(package) = package_target(package)
                            && exported(package, symbol)
                            && let Some(targets) = declarations
                                .get(&package)
                                .and_then(|declarations| declarations.get(symbol))
                        {
                            candidates.extend(targets.iter().copied());
                        }
                    }
                }
            } else if matches!(kind.as_str(), "package" | "load")
                && let Some(package) = package_target(value)
            {
                for &target in &index.packages[package].targets {
                    if references.get(target).is_some_and(|reference| {
                        reference.exports.iter().any(|name| exported(package, name))
                    }) {
                        edges.push((file, target));
                    }
                }
            }
            candidates.sort_unstable();
            candidates.dedup();
            if let [target] = candidates.as_slice() {
                edges.push((file, *target));
            }
        }
    }
    local::finish(edges)
}
