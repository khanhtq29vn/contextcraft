//! CMake command/function/target outlines and static local file dependencies.
//!
//! Resolves literal `include`, `add_subdirectory`, and target source paths without
//! executing CMake. Includes keep the caller's source directory; subdirectories
//! establish a new one. Current-list/current-source directory variables are known;
//! unconditional literal set/list variables are propagated without evaluation.
//! Computed variables, module search paths, generated files, and deferred function
//! or macro calls are not inferred. Standalone scripts use the repository root.

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

/// CMake structural outlines.
#[derive(Debug)]
pub struct CMake;

impl Language for CMake {
    fn id(&self) -> &'static str {
        "cmake"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_cmake::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/cmake.scm")
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
        name == "CMakeLists.txt"
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".cmake"]
    }
}

fn arguments(node: ts::Node<'_>, source: &[u8]) -> Vec<Option<String>> {
    let mut cursor = node.walk();
    let Some(list) = node
        .named_children(&mut cursor)
        .find(|node| node.kind() == "argument_list")
    else {
        return Vec::new();
    };
    let mut cursor = list.walk();
    list.named_children(&mut cursor)
        .filter(|node| node.kind() == "argument")
        .map(|node| {
            let value = node.named_child(0)?;
            let raw = text(value, source);
            let value = match value.kind() {
                "quoted_argument" => raw.strip_prefix('"')?.strip_suffix('"')?,
                "bracket_argument" => {
                    let mut cursor = value.walk();
                    let content = value
                        .named_children(&mut cursor)
                        .find(|node| node.kind() == "bracket_argument_content")?;
                    let raw = text(content, source);
                    if raw.contains('$') {
                        return None;
                    }
                    raw.strip_prefix("\r\n")
                        .or_else(|| raw.strip_prefix('\n'))
                        .unwrap_or(raw)
                }
                "unquoted_argument" => raw,
                _ => return None,
            };
            (!value.contains(['\\', '\n', '\r', '\0'])).then(|| value.to_owned())
        })
        .collect()
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.has_error() {
            continue;
        }
        let mut ancestor = node.parent();
        let mut deferred = false;
        let mut conditional = false;
        while let Some(node) = ancestor {
            deferred |= matches!(node.kind(), "function_def" | "macro_def");
            conditional |= matches!(
                node.kind(),
                "if_condition" | "foreach_loop" | "while_loop" | "block_def"
            );
            ancestor = node.parent();
        }
        if deferred {
            continue;
        }
        let Some(name) = node
            .named_child(0)
            .filter(|node| node.kind() == "identifier")
        else {
            continue;
        };
        let name = text(name, source).to_ascii_lowercase();
        if !matches!(
            name.as_str(),
            "include"
                | "add_subdirectory"
                | "add_library"
                | "add_executable"
                | "target_sources"
                | "target_link_libraries"
                | "set"
                | "unset"
        ) {
            if !matches!(
                name.as_str(),
                "cmake_minimum_required"
                    | "message"
                    | "target_include_directories"
                    | "target_compile_definitions"
                    | "target_compile_options"
                    | "target_compile_features"
            ) {
                references.imports.push(("unknown".into(), String::new()));
            }
            continue;
        }
        let args = arguments(node, source);
        let Some(Some(first)) = args.first() else {
            continue;
        };
        if matches!(name.as_str(), "set" | "unset") {
            let literal = name == "set"
                && !conditional
                && args.iter().all(Option::is_some)
                && !args
                    .iter()
                    .flatten()
                    .any(|arg| matches!(arg.as_str(), "CACHE" | "PARENT_SCOPE"));
            references.imports.push((
                format!("set:{first}"),
                if literal {
                    args.iter()
                        .skip(1)
                        .flatten()
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(";")
                } else {
                    "$UNKNOWN".into()
                },
            ));
            continue;
        }
        if matches!(name.as_str(), "add_library" | "add_executable") {
            references.exports.push(first.clone());
        }
        if name == "target_sources" {
            references.imports.push(("target".into(), first.clone()));
        }
        if args.get(1).and_then(Option::as_deref) == Some("ALIAS")
            && let Some(Some(target)) = args.get(2)
        {
            references.imports.push(("target".into(), target.clone()));
        }
        if name == "target_link_libraries" {
            references.imports.extend(
                args.iter()
                    .skip(1)
                    .flatten()
                    .filter(|name| {
                        !matches!(
                            name.as_str(),
                            "PRIVATE" | "PUBLIC" | "INTERFACE" | "debug" | "optimized" | "general"
                        )
                    })
                    .map(|name| ("target".into(), name.clone())),
            );
            continue;
        }
        match name.as_str() {
            "include" => references.imports.push(("include".into(), first.clone())),
            "add_subdirectory" => references
                .imports
                .push(("subdirectory".into(), first.clone())),
            _ => {
                if args
                    .iter()
                    .flatten()
                    .any(|argument| matches!(argument.as_str(), "IMPORTED" | "ALIAS"))
                {
                    continue;
                }
                for path in args.iter().skip(1).flatten() {
                    if matches!(
                        path.as_str(),
                        "PRIVATE"
                            | "PUBLIC"
                            | "INTERFACE"
                            | "STATIC"
                            | "SHARED"
                            | "MODULE"
                            | "OBJECT"
                            | "UNKNOWN"
                            | "EXCLUDE_FROM_ALL"
                            | "WIN32"
                            | "MACOSX_BUNDLE"
                            | "FILE_SET"
                            | "TYPE"
                            | "HEADERS"
                            | "CXX_MODULES"
                            | "BASE_DIRS"
                            | "FILES"
                    ) {
                        continue;
                    }
                    references.imports.push(("source".into(), path.clone()));
                }
            }
        }
    }
    references
}

fn path(
    index: &Index,
    file: FileId,
    source_dir: &std::path::Path,
    value: &str,
) -> Option<std::path::PathBuf> {
    let value = value
        .replace(
            "${CMAKE_CURRENT_LIST_DIR}",
            &index
                .root
                .join(index.files[file].path.parent().unwrap())
                .to_string_lossy(),
        )
        .replace(
            "${CMAKE_CURRENT_SOURCE_DIR}",
            &index.root.join(source_dir).to_string_lossy(),
        );
    (!value.is_empty() && !value.contains(['$', ';']) && !value.contains("://"))
        .then(|| source_dir.join(value))
}

/// Includes share variables with the caller; subdirectories receive a copy.
fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut resolver = Resolver {
        index,
        references,
        files: local::readable_files(index, repository),
        edges: Vec::new(),
        active: std::collections::HashSet::new(),
        reached: std::collections::HashSet::new(),
        scope: std::collections::HashSet::new(),
        steps: 0,
    };
    let mut roots: Vec<_> = references.iter().map(|(file, _)| file).collect();
    roots.sort_by_key(|file| {
        index.files[*file]
            .path
            .file_name()
            .is_none_or(|name| name != "CMakeLists.txt")
    });
    let mut scopes = Vec::new();
    for file in roots {
        let entry = index.files[file]
            .path
            .file_name()
            .is_some_and(|name| name == "CMakeLists.txt");
        if !entry && resolver.reached.contains(&file) {
            continue;
        }
        let directory = if entry {
            index.files[file].path.parent().unwrap()
        } else {
            std::path::Path::new("")
        };
        resolver.scope.clear();
        resolver.walk(file, directory, &mut std::collections::HashMap::new());
        scopes.push(resolver.scope.clone());
    }
    for scope in scopes {
        for &file in &scope {
            let Some(reference) = references.get(file) else {
                continue;
            };
            for (kind, name) in &reference.imports {
                if kind != "target" || name.contains('$') {
                    continue;
                }
                let targets: Vec<_> = scope
                    .iter()
                    .filter(|target| {
                        references
                            .get(**target)
                            .is_some_and(|reference| reference.exports.contains(name))
                    })
                    .copied()
                    .collect();
                if let [target] = targets.as_slice() {
                    resolver.edges.push((file, *target));
                }
            }
        }
    }
    local::finish(resolver.edges)
}

// Bound static substitutions and environments before following recursive includes.
const LITERAL_LIMIT: usize = 1_048_576;

struct Resolver<'a> {
    index: &'a Index,
    references: &'a ArenaMap<FileId, References>,
    files: std::collections::HashMap<&'a std::path::Path, FileId>,
    edges: Vec<(FileId, FileId)>,
    active: std::collections::HashSet<(FileId, std::path::PathBuf)>,
    reached: std::collections::HashSet<FileId>,
    scope: std::collections::HashSet<FileId>,
    steps: usize,
}

impl Resolver<'_> {
    fn walk(
        &mut self,
        file: FileId,
        source_dir: &std::path::Path,
        variables: &mut std::collections::HashMap<String, String>,
    ) {
        let context = (file, source_dir.to_path_buf());
        if self.active.len() >= 256 || !self.active.insert(context.clone()) {
            return;
        }
        self.reached.insert(file);
        self.scope.insert(file);
        if let Some(references) = self.references.get(file) {
            for (kind, raw) in &references.imports {
                self.steps += 1;
                if self.steps > 100_000 {
                    break;
                }
                if kind == "unknown" {
                    variables.clear();
                    continue;
                }
                let value = expand(raw, variables).map(|value| {
                    value
                        .replace(
                            "${CMAKE_CURRENT_LIST_DIR}",
                            &self
                                .index
                                .root
                                .join(self.index.files[file].path.parent().unwrap())
                                .to_string_lossy(),
                        )
                        .replace(
                            "${CMAKE_CURRENT_SOURCE_DIR}",
                            &self.index.root.join(source_dir).to_string_lossy(),
                        )
                });
                if let Some(name) = kind.strip_prefix("set:") {
                    if let Some(value) = value.filter(|value| {
                        value.len()
                            + variables
                                .iter()
                                .filter(|(key, _)| key.as_str() != name)
                                .map(|(_, value)| value.len())
                                .sum::<usize>()
                            <= LITERAL_LIMIT
                    }) {
                        variables.insert(name.into(), value);
                    } else {
                        variables.remove(name);
                    }
                    continue;
                }
                let Some(value) = value else {
                    if kind == "include" {
                        variables.clear();
                    }
                    continue;
                };
                if kind == "target" {
                    continue;
                }
                for value in value.split(';') {
                    if kind == "include"
                        && !value.contains(['/', '\\'])
                        && std::path::Path::new(value).extension().is_none()
                    {
                        variables.clear();
                        continue;
                    }
                    let Some(mut target_path) = path(self.index, file, source_dir, value) else {
                        continue;
                    };
                    if kind == "subdirectory" {
                        target_path.push("CMakeLists.txt");
                    }
                    if let Some(target) = local::find(self.index, &self.files, &target_path) {
                        self.edges.push((file, target));
                        if kind == "include" {
                            self.walk(target, source_dir, variables);
                        } else if kind == "subdirectory" {
                            let directory = self.index.files[target].path.parent().unwrap();
                            self.walk(target, directory, &mut variables.clone());
                        }
                    }
                }
            }
        }
        self.active.remove(&context);
    }
}

fn expand(value: &str, variables: &std::collections::HashMap<String, String>) -> Option<String> {
    // Repeated literal substitutions can otherwise grow exponentially.
    if value.len() > LITERAL_LIMIT {
        return None;
    }
    let mut result = String::new();
    let mut remaining = value;
    while let Some(start) = remaining.find("${") {
        result.push_str(&remaining[..start]);
        let tail = &remaining[start + 2..];
        let end = tail.find('}')?;
        let name = &tail[..end];
        if matches!(name, "CMAKE_CURRENT_LIST_DIR" | "CMAKE_CURRENT_SOURCE_DIR") {
            result.push_str(&remaining[start..start + 3 + end]);
        } else {
            let replacement = variables.get(name)?;
            if result.len() + replacement.len() > LITERAL_LIMIT {
                return None;
            }
            result.push_str(replacement);
        }
        if result.len() > LITERAL_LIMIT {
            return None;
        }
        remaining = &tail[end + 1..];
    }
    if result.len() + remaining.len() > LITERAL_LIMIT {
        return None;
    }
    result.push_str(remaining);
    let unresolved = result
        .replace("${CMAKE_CURRENT_LIST_DIR}", "")
        .replace("${CMAKE_CURRENT_SOURCE_DIR}", "");
    (!unresolved.contains('$')).then_some(result)
}
