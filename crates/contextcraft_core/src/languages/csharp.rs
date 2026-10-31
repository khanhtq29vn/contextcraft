//! C# outlines, .NET project references, and solution membership.
//!
//! Reads `.csproj`, `.sln`, and `.slnx` files, including static Compile membership.
//! Local namespace/type imports are restricted to visible projects. Build conditions
//! contribute possible dependencies; MSBuild property expressions, imported build
//! logic, generated code, and compiler-level type binding are not evaluated.

use tree_sitter as ts;

pub mod manifest;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::FileId;
use crate::index::Index;
use crate::package::PackageResolution;
use crate::repo::{Analysis, Repository};
use la_arena::ArenaMap;
use local::{References, text};

/// CSharp grammar and local project analysis.
#[derive(Debug)]
pub struct CSharp;

impl Language for CSharp {
    fn id(&self) -> &'static str {
        "csharp"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_c_sharp::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/csharp.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(local::DependencyAnalysis::new(extract, resolve))
    }

    fn discover_packages(
        &self,
        index: &Index,
        _config: &Config,
    ) -> Result<Vec<crate::package::Package>, Error> {
        let packages = local::discover(index, "csharp", &["csproj"], &[]);
        for package in &packages {
            if package.manifests.len() > 1 {
                return Err(Error::Manifest {
                    path: package.manifests[0].clone(),
                    message:
                        "multiple C# projects in one directory have ambiguous source ownership"
                            .into(),
                });
            }
        }
        Ok(packages)
    }

    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, false)
    }

    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_outline(source, analysis, true)
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        manifest::discover(index, config)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "Directory.Build.props",
            "Directory.Build.targets",
            "Directory.Packages.props",
            "global.json",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".cs"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let mut file_namespace = String::new();

    for &node in nodes {
        if node.kind() == "file_scoped_namespace_declaration"
            && let Some(name) = node.child_by_field_name("name")
        {
            file_namespace = text(name, source).into();
        }
    }

    for &node in nodes {
        if node.kind() == "using_directive" {
            let directive = text(node, source);
            let mut name = directive
                .trim_start_matches("global ")
                .trim_start_matches("using ")
                .trim()
                .trim_end_matches(';')
                .trim();
            let kind = if name.starts_with("static ") {
                "type"
            } else {
                "namespace"
            };
            name = name
                .trim_start_matches("static ")
                .trim_start_matches("unsafe ")
                .trim();
            if let Some((_, value)) = name.split_once('=') {
                name = value.trim();
            }
            references.imports.push((
                if directive.starts_with("global ") {
                    format!("global:{kind}")
                } else {
                    kind.into()
                },
                name.trim_start_matches("global::").into(),
            ));
            continue;
        }

        let Some(name) = node.child_by_field_name("name") else {
            continue;
        };
        let mut parts = vec![text(name, source).to_owned()];
        let mut parent = node.parent();
        while let Some(ancestor) = parent {
            if matches!(
                ancestor.kind(),
                "namespace_declaration"
                    | "class_declaration"
                    | "struct_declaration"
                    | "record_declaration"
            ) && let Some(name) = ancestor.child_by_field_name("name")
            {
                parts.push(text(name, source).into());
            }
            parent = ancestor.parent();
        }
        if !file_namespace.is_empty() && node.kind() != "file_scoped_namespace_declaration" {
            parts.push(file_namespace.clone());
        }
        parts.reverse();
        references.exports.push(parts.join("."));
    }

    references
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let compiled: std::collections::HashSet<_> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("csharp"))
        .flat_map(|(_, package)| package.targets.iter().copied())
        .collect();
    let mut references: ArenaMap<_, _> = references
        .iter()
        .filter(|(file, _)| {
            compiled.contains(file)
                || index.packages[index.files[*file].package_id].language != Some("csharp")
        })
        .map(|(file, reference)| (file, reference.clone()))
        .collect();
    let mut global = std::collections::HashMap::<_, Vec<_>>::new();
    for (file, references) in references.iter() {
        for (kind, name) in &references.imports {
            if let Some(kind) = kind.strip_prefix("global:") {
                global
                    .entry(index.files[file].package_id)
                    .or_default()
                    .push((kind.to_owned(), name.clone()));
            }
        }
    }
    for (file, references) in references.iter_mut() {
        if let Some(imports) = global.get(&index.files[file].package_id) {
            references.imports.extend(imports.iter().cloned());
        }
    }
    local::resolve_symbols(index, repository, &references)
}
