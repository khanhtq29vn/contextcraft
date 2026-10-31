//! Containerfile/Dockerfile outlines using `tree-sitter-containerfile`.
//!
//! Root-level build files use the repository root as their conventional build
//! context. COPY/ADD edges honor the applicable Docker ignore file. Nested build
//! files, external contexts/stages, ONBUILD payloads, and expanded paths remain
//! unresolved because their build context is not declared by the source file.

use std::path::{Component, Path, PathBuf};
use std::sync::{Arc, Mutex};

use globset::GlobMatcher;
use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis, local, render_outline};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::{PackageResolution, local_path};
use crate::repo::{Analysis, Repository};

#[derive(Debug)]
struct IgnoreRule {
    pattern: GlobMatcher,
    include: bool,
}

type Ignores = ArenaMap<FileId, Option<Vec<IgnoreRule>>>;

/// Containerfile grammar with explicitly bounded local build-context resolution.
#[derive(Debug, Default)]
pub struct Dockerfile {
    ignores: Arc<Ignores>,
}

impl Language for Dockerfile {
    fn id(&self) -> &'static str {
        "dockerfile"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_containerfile::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/dockerfile.scm")
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(DockerAnalysis {
            copies: Mutex::new(ArenaMap::new()),
            ignores: Arc::clone(&self.ignores),
        })
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
        let mut ignores = ArenaMap::new();
        for (id, file) in index.files.iter().filter(|(_, file)| {
            file.language == Some("dockerfile")
                && file
                    .path
                    .parent()
                    .is_some_and(|path| path.as_os_str().is_empty())
        }) {
            let specific = PathBuf::from(format!("{}.dockerignore", file.path.display()));
            let mut rules = Some(Vec::new());
            for candidate in [specific.as_path(), Path::new(".dockerignore")] {
                match std::fs::symlink_metadata(index.root.join(candidate)) {
                    Ok(_) => {
                        rules = if let Some(path) = local_path(index, candidate) {
                            local::read(index, &path, config)?
                                .and_then(|source| ignore_rules(&source))
                        } else {
                            None
                        };
                        break;
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                    Err(source) => {
                        return Err(Error::Io {
                            path: index.root.join(candidate),
                            source,
                        });
                    }
                }
            }
            ignores.insert(id, rules);
        }
        self.ignores = Arc::new(ignores);
        Ok(PackageResolution::default())
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &[]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[".dockerignore"]
    }

    fn matches_filename(&self, name: &str) -> bool {
        !name.ends_with(".dockerignore")
            && ["Dockerfile", "Containerfile"].iter().any(|base| {
                name == *base
                    || name
                        .strip_prefix(base)
                        .is_some_and(|suffix| suffix.starts_with('.') && suffix.len() > 1)
            })
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".dockerfile", ".containerfile"]
    }
}

fn ignore_rules(source: &str) -> Option<Vec<IgnoreRule>> {
    let mut rules = Vec::new();
    for line in source.trim_start_matches('\u{feff}').lines() {
        if line.starts_with('#') {
            continue;
        }
        let line = line.trim();
        let (include, pattern) = if let Some(pattern) = line.strip_prefix('!') {
            (true, pattern.trim())
        } else {
            (false, line)
        };
        let pattern = pattern.trim_matches('/');
        if pattern.is_empty() || pattern == "." {
            continue;
        }
        rules.push(IgnoreRule {
            pattern: local::path_glob(Path::new(""), pattern)?,
            include,
        });
    }
    Some(rules)
}

fn excluded(path: &Path, rules: &[IgnoreRule]) -> bool {
    let mut excluded = false;
    for rule in rules {
        if path.ancestors().any(|path| rule.pattern.is_match(path)) {
            excluded = !rule.include;
        }
    }
    excluded
}

#[derive(Debug)]
struct Copy {
    sources: Vec<String>,
    excludes: Vec<GlobMatcher>,
}

#[derive(Debug)]
struct DockerAnalysis {
    copies: Mutex<ArenaMap<FileId, Vec<Copy>>>,
    ignores: Arc<Ignores>,
}

impl LanguageAnalysis for DockerAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut copies = Vec::new();
        for &node in nodes {
            if !matches!(node.kind(), "copy_instruction" | "add_instruction") {
                continue;
            }
            if node
                .parent()
                .is_some_and(|parent| parent.kind() == "onbuild_instruction")
            {
                continue;
            }
            let mut cursor = node.walk();
            let children: Vec<_> = node.named_children(&mut cursor).collect();
            let params: Vec<_> = children
                .iter()
                .filter(|node| node.kind() == "param")
                .map(|node| local::text(*node, source))
                .collect();
            if params.iter().any(|value| value.starts_with("--from")) {
                continue;
            }
            let mut excludes = Vec::new();
            let mut unknown = false;
            for pattern in params
                .iter()
                .filter_map(|param| param.strip_prefix("--exclude="))
            {
                if pattern.contains('$') {
                    unknown = true;
                    break;
                }
                if let Some(pattern) = local::path_glob(Path::new(""), pattern) {
                    excludes.push(pattern);
                } else {
                    unknown = true;
                }
            }
            if unknown {
                continue;
            }
            let mut paths = Vec::new();
            for child in &children {
                if child.kind() == "json_string_array" {
                    if let Ok(values) =
                        serde_json::from_str::<Vec<String>>(local::text(*child, source))
                    {
                        paths.extend(values);
                    }
                } else if child.kind() == "path" {
                    let value = local::text(*child, source);
                    let value = if value.starts_with('"') {
                        serde_json::from_str::<String>(value).ok()
                    } else if value.starts_with('\'') {
                        value
                            .strip_prefix('\'')
                            .and_then(|value| value.strip_suffix('\''))
                            .map(str::to_owned)
                    } else {
                        Some(value.to_owned())
                    };
                    if let Some(value) = value {
                        paths.push(value);
                    }
                }
            }
            paths.pop();
            paths.retain(|path| {
                !path.is_empty()
                    && !path.contains(['$', '\\', '\0'])
                    && !path.contains("://")
                    && !["<<", "git@", "~"]
                        .iter()
                        .any(|prefix| path.starts_with(prefix))
                    && !Path::new(path)
                        .components()
                        .any(|component| component == Component::ParentDir)
            });
            copies.push(Copy {
                sources: paths,
                excludes,
            });
        }
        self.copies.lock().unwrap().insert(file, copies);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let files = local::readable_files(index, repository);
        let mut edges = Vec::new();
        for (file, copies) in self.copies.lock().unwrap().iter() {
            let Some(Some(ignores)) = self.ignores.get(file) else {
                continue;
            };
            for copy in copies {
                for source in &copy.sources {
                    let source = source.trim_start_matches('/');
                    let pattern = local::path_glob(Path::new(""), source);
                    let direct = (!source.contains(['*', '?', '[']))
                        .then(|| local_path(index, Path::new(source)))
                        .flatten();
                    for (&path, &target) in &files {
                        let matched = direct
                            .as_ref()
                            .is_some_and(|source| path == source || path.starts_with(source))
                            || pattern.as_ref().is_some_and(|pattern| {
                                path.ancestors().any(|path| pattern.is_match(path))
                            });
                        if matched
                            && !excluded(path, ignores)
                            && !copy
                                .excludes
                                .iter()
                                .any(|pattern| path.ancestors().any(|path| pattern.is_match(path)))
                        {
                            edges.push((file, target));
                        }
                    }
                }
            }
        }
        local::finish(edges)
    }
}
