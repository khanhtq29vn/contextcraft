//! Shared mechanics for static, repository-local language resolution.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::LanguageAnalysis;
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::{Package, local_path};
use crate::repo::Repository;

#[derive(Debug, Default, Clone)]
pub(super) struct References {
    pub imports: Vec<(String, String)>,
    pub exports: Vec<String>,
}

type Extract = fn(&[ts::Node<'_>], &[u8]) -> References;
type Resolve = fn(&Index, &Repository, &ArenaMap<FileId, References>) -> Vec<(FileId, FileId)>;

#[derive(Debug)]
pub(super) struct DependencyAnalysis {
    references: Mutex<ArenaMap<FileId, References>>,
    extract: Extract,
    resolve: Resolve,
}

impl DependencyAnalysis {
    pub fn new(extract: Extract, resolve: Resolve) -> Self {
        Self {
            references: Mutex::new(ArenaMap::new()),
            extract,
            resolve,
        }
    }
}

impl LanguageAnalysis for DependencyAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let references = (self.extract)(nodes, source);
        self.references.lock().unwrap().insert(file, references);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        (self.resolve)(index, repository, &self.references.lock().unwrap())
    }
}

pub(super) fn text<'a>(node: ts::Node<'_>, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

pub(super) fn visit<'tree>(node: ts::Node<'tree>, mut visitor: impl FnMut(ts::Node<'tree>)) {
    let mut stack = vec![node];

    while let Some(node) = stack.pop() {
        visitor(node);
        let mut cursor = node.walk();
        stack.extend(node.named_children(&mut cursor));
    }
}

/// Only accepts literal strings without interpolation or escape evaluation.
pub(super) fn literal(node: ts::Node<'_>, source: &[u8]) -> Option<String> {
    if !matches!(node.kind(), "string" | "raw_string" | "line_string_literal") {
        return None;
    }

    let value = text(node, source);
    let quote = value.as_bytes().first()?;

    if !matches!(quote, b'\'' | b'"') || value.as_bytes().last()? != quote || value.len() < 2 {
        return None;
    }

    let value = &value[1..value.len() - 1];
    (!value.contains(['\\', '\n', '\r', '\0']) && !value.contains("#{") && !value.contains("${"))
        .then(|| value.to_owned())
}

pub(super) fn read(
    index: &Index,
    manifest: &Path,
    config: &Config,
) -> Result<Option<String>, Error> {
    let path = index.root.join(manifest);
    let mut bytes = Vec::new();
    fs::File::open(&path)
        .and_then(|file| {
            file.take((config.max_file_size_bytes.get() as u64).saturating_add(1))
                .read_to_end(&mut bytes)
        })
        .map_err(|source| Error::Io { path, source })?;

    if bytes.len() > config.max_file_size_bytes.get() {
        return Ok(None);
    }

    String::from_utf8(bytes)
        .map(Some)
        .map_err(|error| Error::Manifest {
            path: manifest.to_path_buf(),
            message: error.to_string(),
        })
}

pub(super) fn parse(grammar: ts::Language, source: &str) -> Result<ts::Tree, Error> {
    let mut parser = ts::Parser::new();
    parser.set_language(&grammar)?;
    parser.parse(source, None).ok_or(Error::Parse)
}

pub(super) fn package(root: PathBuf, language: &'static str, manifest: PathBuf) -> Package {
    Package {
        root,
        name: None,
        language: Some(language),
        manifests: vec![manifest],
        targets: Vec::new(),
        dependencies: Vec::new(),
    }
}

pub(super) fn visible(index: &Index, package: PackageId) -> HashSet<PackageId> {
    let mut seen = HashSet::from([package]);
    let mut stack = vec![package];

    while let Some(package) = stack.pop() {
        for dependency in &index.packages[package].dependencies {
            if seen.insert(dependency.package) {
                stack.push(dependency.package);
            }
        }
    }

    seen
}

pub(super) fn file_lookup<'a>(
    index: &'a Index,
    repository: &Repository,
    language: &str,
) -> HashMap<&'a Path, FileId> {
    index
        .files
        .iter()
        .filter(|(id, file)| {
            file.language == Some(language) && repository.sources.get(*id).is_some()
        })
        .map(|(id, file)| (file.path.as_path(), id))
        .collect()
}

pub(super) fn readable_files<'a>(
    index: &'a Index,
    repository: &Repository,
) -> HashMap<&'a Path, FileId> {
    index
        .files
        .iter()
        .filter(|(id, _)| repository.sources.get(*id).is_some())
        .map(|(id, file)| (file.path.as_path(), id))
        .collect()
}

pub(super) fn find(index: &Index, files: &HashMap<&Path, FileId>, path: &Path) -> Option<FileId> {
    local_path(index, path).and_then(|path| files.get(path.as_path()).copied())
}

pub(super) fn path_glob(base: &Path, pattern: &str) -> Option<globset::GlobMatcher> {
    let mut path = PathBuf::new();
    for component in base.join(pattern).components() {
        match component {
            std::path::Component::Normal(value) => path.push(value),
            std::path::Component::CurDir => {}
            std::path::Component::ParentDir => {
                if !path.pop() {
                    return None;
                }
            }
            _ => return None,
        }
    }
    let pattern = path
        .to_string_lossy()
        .replace('{', "\\{")
        .replace('}', "\\}");
    globset::GlobBuilder::new(&pattern)
        .literal_separator(true)
        .backslash_escape(true)
        .build()
        .ok()
        .map(|glob| glob.compile_matcher())
}

pub(super) fn finish(mut edges: Vec<(FileId, FileId)>) -> Vec<(FileId, FileId)> {
    edges.retain(|(from, to)| from != to);
    edges.sort_unstable();
    edges.dedup();
    edges
}

/// Resolves explicit namespace/type imports only within visible local projects.
pub(super) fn resolve_symbols(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut exports: BTreeMap<&str, Vec<FileId>> = BTreeMap::new();

    for (file, reference) in references.iter() {
        for name in &reference.exports {
            exports.entry(name).or_default().push(file);
        }
    }

    let mut edges = Vec::new();
    let mut visibility = HashMap::new();
    let mut owners: HashMap<FileId, Vec<PackageId>> = HashMap::new();
    for (package, metadata) in index.packages.iter() {
        for &file in &metadata.targets {
            owners.entry(file).or_default().push(package);
        }
    }
    for (file, _) in references.iter() {
        owners
            .entry(file)
            .or_insert_with(|| vec![index.files[file].package_id]);
    }

    for (file, reference) in references.iter() {
        for &package in &owners[&file] {
            let visible = visibility
                .entry(package)
                .or_insert_with(|| visible(index, package));
            for (kind, name) in &reference.imports {
                let prefix = format!("{name}.");
                let descendants = exports
                    .range(prefix.as_str()..)
                    .take_while(|(export, _)| export.starts_with(&prefix))
                    .filter(|_| kind == "namespace")
                    .map(|(_, targets)| targets);
                for targets in exports.get(name.as_str()).into_iter().chain(descendants) {
                    for &target in targets {
                        if owners[&target].iter().any(|owner| visible.contains(owner))
                            && repository.sources.get(target).is_some()
                        {
                            edges.push((file, target));
                        }
                    }
                }
            }
        }
    }

    finish(edges)
}

pub(super) fn discover(
    index: &Index,
    language: &'static str,
    extensions: &[&str],
    filenames: &[&str],
) -> Vec<Package> {
    let mut packages = std::collections::BTreeMap::new();

    for (_, file) in index.files.iter() {
        let named = file
            .path
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| filenames.contains(&name));
        let extension = file
            .path
            .extension()
            .and_then(|extension| extension.to_str())
            .is_some_and(|extension| extensions.contains(&extension));
        if !named && !extension {
            continue;
        }
        let root = file.path.parent().unwrap().to_path_buf();
        let package = packages
            .entry(root.clone())
            .or_insert_with(|| package(root, language, file.path.clone()));
        if !package.manifests.contains(&file.path) {
            package.manifests.push(file.path.clone());
        }
    }

    packages.into_values().collect()
}

/// Resolves literal file references relative to the importing file.
pub(super) fn resolve_relative(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = readable_files(index, repository);
    let mut edges = Vec::new();
    for (file, references) in references.iter() {
        for (_, path) in &references.imports {
            if let Some(target) = find(
                index,
                &files,
                &index.files[file].path.parent().unwrap().join(path),
            ) {
                edges.push((file, target));
            }
        }
    }
    finish(edges)
}

/// Reads literal YAML configuration without resolving tags, aliases, or executable extensions.
pub(super) fn yaml_config(source: &str) -> Option<serde_json::Value> {
    fn value(node: ts::Node<'_>, source: &[u8]) -> Option<serde_json::Value> {
        use serde_json::Value;
        let mut cursor = node.walk();
        let children: Vec<_> = node
            .named_children(&mut cursor)
            .filter(|node| node.kind() != "comment")
            .collect();
        match node.kind() {
            "stream" | "document" | "block_node" | "flow_node" | "block_sequence_item" => {
                if let [child] = children.as_slice() {
                    value(*child, source)
                } else if children.is_empty() {
                    Some(Value::Null)
                } else {
                    None
                }
            }
            "block_mapping" | "flow_mapping" => {
                let mut result = serde_json::Map::new();
                for pair in children {
                    let key = value(pair.child_by_field_name("key")?, source)?
                        .as_str()?
                        .to_owned();
                    let item = value(pair.child_by_field_name("value")?, source)?;
                    if result.insert(key, item).is_some() {
                        return None;
                    }
                }
                Some(Value::Object(result))
            }
            "block_sequence" | "flow_sequence" => children
                .into_iter()
                .map(|node| value(node, source))
                .collect::<Option<Vec<_>>>()
                .map(Value::Array),
            "plain_scalar" => Some(Value::String(text(node, source).to_owned())),
            "double_quote_scalar" => serde_json::from_str(text(node, source)).ok(),
            "single_quote_scalar" => Some(Value::String(
                text(node, source)
                    .strip_prefix('\'')?
                    .strip_suffix('\'')?
                    .replace("''", "'"),
            )),
            _ => None,
        }
    }
    let tree = parse(tree_sitter_yaml::LANGUAGE.into(), source).ok()?;
    if tree.root_node().has_error() {
        return None;
    }
    value(tree.root_node(), source.as_bytes())
}
