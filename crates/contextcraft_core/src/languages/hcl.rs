//! HCL outlines and Terraform directory-module dependencies.
//!
//! Terraform `.tf` files share a module per directory. Literal local module
//! sources and unambiguous configuration traversals produce file dependencies.
//! Remote sources, templates, and iteration-scoped traversals are not evaluated.

use tree_sitter as ts;

use super::local::{self, References, text};
use super::{Language, LanguageAnalysis, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::{Package, PackageDependency, PackageResolution, local_path};
use crate::repo::Analysis;
use crate::repo::Repository;
use la_arena::ArenaMap;

/// Hcl structural outlines and static local dependencies.
#[derive(Debug)]
pub struct Hcl;

impl Language for Hcl {
    fn id(&self) -> &'static str {
        "hcl"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_hcl::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/hcl.scm")
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

    fn discover_packages(&self, index: &Index, _config: &Config) -> Result<Vec<Package>, Error> {
        Ok(local::discover(index, "hcl", &["tf"], &[]))
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        packages(index, config)
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/.terraform/**",
            "!**/.terraform.lock.hcl",
            "!**/*.tfstate",
            "!**/*.tfstate.*",
            "!**/*.tfplan",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".hcl", ".tf", ".tfvars"]
    }
}

fn string(node: ts::Node<'_>, source: &[u8]) -> Option<String> {
    if node.kind() != "string_lit" {
        return None;
    }
    let value: String = serde_json::from_str(text(node, source)).ok()?;
    (!value.contains("${") && !value.contains("%{")).then_some(value)
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "variable_expr" {
            let mut parts = vec![text(node, source).to_owned()];
            let mut sibling = node.next_named_sibling();
            while let Some(node) = sibling.filter(|node| node.kind() == "get_attr") {
                if let Some(name) = node.named_child(0) {
                    parts.push(text(name, source).into());
                }
                sibling = node.next_named_sibling();
            }
            let count = if parts[0] == "data" { 3 } else { 2 };
            if parts.len() >= count {
                let mut ancestor = node.parent();
                let mut in_loop = false;
                while let Some(node) = ancestor {
                    in_loop |= matches!(node.kind(), "for_expr" | "template_for" | "dynamic_block");
                    ancestor = node.parent();
                }
                if !in_loop {
                    references
                        .imports
                        .push(("symbol".into(), parts[..count].join(".")));
                }
            }
            continue;
        }
        if node.kind() != "block"
            || node
                .parent()
                .and_then(|node| node.parent())
                .is_none_or(|node| node.kind() != "config_file")
        {
            continue;
        }
        let mut cursor = node.walk();
        let children: Vec<_> = node.named_children(&mut cursor).collect();
        let Some(kind) = children.iter().find(|node| node.kind() == "identifier") else {
            continue;
        };
        let labels: Vec<_> = children
            .iter()
            .filter_map(|node| string(*node, source))
            .collect();
        let kind = text(*kind, source);
        let key = match (kind, labels.as_slice()) {
            ("resource", [kind, name]) => Some(format!("{kind}.{name}")),
            ("data", [kind, name]) => Some(format!("data.{kind}.{name}")),
            ("variable", [name]) => Some(format!("var.{name}")),
            ("module", [name]) => Some(format!("module.{name}")),
            _ => None,
        };
        if let Some(key) = key {
            references.exports.push(key);
        }
        let Some(body) = children.iter().find(|node| node.kind() == "body") else {
            continue;
        };
        let mut cursor = body.walk();
        for attribute in body
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "attribute")
        {
            let Some(name) = attribute.named_child(0) else {
                continue;
            };
            if kind == "locals" {
                references
                    .exports
                    .push(format!("local.{}", text(name, source)));
            }
            if kind == "module" && text(name, source) == "source" {
                let Some(value) = attribute
                    .named_child(1)
                    .and_then(|node| node.named_child(0))
                    .and_then(|node| node.named_child(0))
                else {
                    continue;
                };
                if let Some(path) = string(value, source)
                    && (path.starts_with("./")
                        || path.starts_with("../")
                        || std::path::Path::new(&path).is_absolute())
                    && let [name] = labels.as_slice()
                {
                    references.imports.push((format!("module:{name}"), path));
                }
            }
        }
    }
    references
}

fn packages(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let roots: std::collections::HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("hcl"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    let files: std::collections::HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    for (&root, &id) in &roots {
        let mut package = index.packages[id].clone();
        package.name = root
            .file_name()
            .map(|name| name.to_string_lossy().into_owned());
        for manifest in &package.manifests {
            package
                .targets
                .extend(files.get(manifest.as_path()).copied());
            let Some(source) = local::read(index, manifest, config)? else {
                continue;
            };
            let tree = local::parse(tree_sitter_hcl::LANGUAGE.into(), &source)?;
            let mut nodes = Vec::new();
            local::visit(tree.root_node(), |node| {
                if node.kind() == "block" {
                    nodes.push(node);
                }
            });
            for (kind, path) in extract(&nodes, source.as_bytes()).imports {
                if let Some(alias) = kind.strip_prefix("module:")
                    && let Some(path) = local_path(index, &root.join(path))
                    && let Some(&target) = roots.get(path.as_path())
                    && target != id
                {
                    package.dependencies.push(PackageDependency {
                        alias: alias.into(),
                        package: target,
                    });
                }
            }
        }
        resolution.packages.insert(id, package);
    }
    Ok(resolution)
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut edges = Vec::new();
    let mut exports = std::collections::HashMap::<_, Vec<_>>::new();
    for (file, references) in references.iter().filter(|(file, _)| {
        index.files[*file]
            .path
            .extension()
            .is_some_and(|extension| extension == "tf")
    }) {
        for name in &references.exports {
            exports
                .entry((index.files[file].package_id, name.as_str()))
                .or_default()
                .push(file);
        }
    }
    for (file, references) in references.iter().filter(|(file, _)| {
        index.files[*file]
            .path
            .extension()
            .is_some_and(|extension| extension == "tf")
    }) {
        let package = &index.packages[index.files[file].package_id];
        for (kind, name) in &references.imports {
            if kind == "symbol" {
                let targets = exports.get(&(index.files[file].package_id, name.as_str()));
                if let Some(targets) = targets
                    && let [target] = targets.as_slice()
                {
                    edges.push((file, *target));
                }
            } else if let Some(alias) = kind.strip_prefix("module:") {
                for dependency in package
                    .dependencies
                    .iter()
                    .filter(|dependency| dependency.alias == alias)
                {
                    for &target in &index.packages[dependency.package].targets {
                        if repository.sources.get(target).is_some() {
                            edges.push((file, target));
                        }
                    }
                }
            }
        }
    }
    local::finish(edges)
}
