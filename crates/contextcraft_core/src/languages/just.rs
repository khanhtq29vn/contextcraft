//! Just outlines, explicit imports/modules, and named recipe dependencies.
//!
//! Imports share their parent recipe scope; modules have independent scopes.
//! A restricted literal-header scanner supplements the pinned grammar for simple
//! namespace-qualified dependencies. Commands, interpolations, computed paths,
//! parameterized namespace calls, and ambiguous definitions are not evaluated.

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

/// Just structural outlines and static local dependencies.
#[derive(Debug)]
pub struct Just;

impl Language for Just {
    fn id(&self) -> &'static str {
        "just"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_just::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/just.scm")
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
        if root.has_error() {
            for ranges in [&mut analysis.sigs, &mut analysis.skel] {
                ranges.retain(|range| {
                    let line = source[..range.start]
                        .iter()
                        .rposition(|byte| *byte == b'\n')
                        .map_or(0, |offset| offset + 1);
                    range.start == line
                });
            }
        }
        analysis
            .sigs
            .extend(headers(root, source).into_iter().map(|header| header.range));
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
        &[".justfile"]
    }

    fn matches_filename(&self, name: &str) -> bool {
        name.eq_ignore_ascii_case("justfile") || name.eq_ignore_ascii_case(".justfile")
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".just"]
    }
}

fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    for &node in nodes {
        if node.kind() == "source_file" {
            for header in headers(node, source) {
                references.exports.push(header.name);
                references.imports.extend(
                    header
                        .dependencies
                        .into_iter()
                        .map(|name| ("recipe".into(), name)),
                );
            }
            continue;
        }
        if node.has_error() {
            continue;
        }

        match node.kind() {
            "import" | "module" => {
                let mut cursor = node.walk();
                let path = node
                    .named_children(&mut cursor)
                    .find(|node| node.kind() == "string");
                let path = if let Some(path) = path {
                    let Some(value) =
                        local::literal(path, source).filter(|path| !path.starts_with("~/"))
                    else {
                        continue;
                    };
                    value
                } else {
                    String::new()
                };
                if node.kind() == "import" {
                    references.imports.push(("import".into(), path));
                } else if let Some(name) = node.child_by_field_name("name") {
                    references
                        .imports
                        .push((format!("module:{}", text(name, source)), path));
                }
            }
            "recipe_header" => {
                if node.start_position().column != 0
                    || node.parent().is_some_and(|node| node.has_error())
                {
                    continue;
                }
                if let Some(name) = node.child_by_field_name("name") {
                    references.exports.push(text(name, source).into());
                }
                local::visit(node, |node| {
                    if matches!(node.kind(), "dependency" | "dependency_expression")
                        && let Some(name) = node.child_by_field_name("name")
                    {
                        references
                            .imports
                            .push(("recipe".into(), text(name, source).into()));
                    }
                });
            }
            "alias" => {
                if node.parent().is_some_and(|node| node.has_error()) {
                    continue;
                }
                if let Some(name) = node.child_by_field_name("left") {
                    references.exports.push(text(name, source).into());
                }
                if let Some(name) = node.child_by_field_name("right") {
                    references
                        .imports
                        .push(("recipe".into(), text(name, source).into()));
                }
            }
            _ => {}
        }
    }
    references
}

fn module_file(
    index: &Index,
    files: &std::collections::HashMap<&std::path::Path, FileId>,
    base: &std::path::Path,
    name: &str,
    explicit: &str,
) -> Option<FileId> {
    let path = base.join(if explicit.is_empty() { name } else { explicit });
    if !explicit.is_empty()
        && let Some(file) = local::find(index, files, &path)
    {
        return Some(file);
    }
    let mut candidates = Vec::new();
    if explicit.is_empty() {
        let mut filename = path.as_os_str().to_os_string();
        filename.push(".just");
        candidates.extend(local::find(index, files, std::path::Path::new(&filename)));
    }
    candidates.extend(local::find(index, files, &path.join("mod.just")));
    if let Some(path) = crate::package::local_path(index, &path) {
        candidates.extend(
            files
                .iter()
                .filter(|(file, _)| {
                    file.parent() == Some(path.as_path())
                        && file
                            .file_name()
                            .and_then(|name| name.to_str())
                            .is_some_and(|name| Just.matches_filename(name))
                })
                .map(|(_, &id)| id),
        );
    }
    candidates.sort_unstable();
    candidates.dedup();
    match candidates.as_slice() {
        [file] => Some(*file),
        _ => None,
    }
}

fn scope(
    root: FileId,
    imports: &std::collections::HashMap<FileId, Vec<FileId>>,
) -> std::collections::HashMap<FileId, usize> {
    let mut depths = std::collections::HashMap::from([(root, 0)]);
    let mut pending = std::collections::VecDeque::from([root]);
    while let Some(file) = pending.pop_front() {
        let depth = depths[&file] + 1;
        for &target in imports.get(&file).into_iter().flatten() {
            if let std::collections::hash_map::Entry::Vacant(entry) = depths.entry(target) {
                entry.insert(depth);
                pending.push_back(target);
            }
        }
    }
    depths
}

fn nearest(candidates: impl Iterator<Item = (usize, FileId)>) -> Option<FileId> {
    let mut depths = std::collections::BTreeMap::<_, std::collections::HashSet<_>>::new();
    for (depth, file) in candidates {
        depths.entry(depth).or_default().insert(file);
    }
    let (_, files) = depths.first_key_value()?;
    (files.len() == 1).then(|| *files.iter().next().unwrap())
}

fn recipe_target(
    name: &str,
    initial: &std::collections::HashMap<FileId, usize>,
    imports: &std::collections::HashMap<FileId, Vec<FileId>>,
    modules: &std::collections::HashMap<FileId, Vec<(String, FileId)>>,
    references: &ArenaMap<FileId, References>,
) -> Option<FileId> {
    let mut parts: Vec<_> = name.split("::").collect();
    let recipe = parts.pop()?;
    let mut visible = initial.clone();
    for name in parts {
        let target = nearest(visible.iter().flat_map(|(&file, &depth)| {
            modules
                .get(&file)
                .into_iter()
                .flatten()
                .filter(move |(module, _)| module == name)
                .map(move |(_, file)| (depth, *file))
        }))?;
        visible = scope(target, imports);
    }
    nearest(visible.iter().filter_map(|(&file, &depth)| {
        references
            .get(file)
            .filter(|references| references.exports.iter().any(|name| name == recipe))
            .map(|_| (depth, file))
    }))
}

fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let files = local::readable_files(index, repository);
    let mut edges = Vec::new();
    let mut imports = std::collections::HashMap::<_, Vec<_>>::new();
    let mut imported = std::collections::HashSet::new();
    let mut modules = std::collections::HashMap::<_, Vec<_>>::new();
    let mut module_roots = std::collections::HashSet::new();
    for (file, references) in references.iter() {
        let base = index.files[file].path.parent().unwrap();
        for (kind, path) in &references.imports {
            if kind == "import" {
                if let Some(target) = local::find(index, &files, &base.join(path)) {
                    edges.push((file, target));
                    imports.entry(file).or_default().push(target);
                    imported.insert(target);
                }
            } else if let Some(name) = kind.strip_prefix("module:")
                && let Some(target) = module_file(index, &files, base, name, path)
            {
                edges.push((file, target));
                modules
                    .entry(file)
                    .or_default()
                    .push((name.to_owned(), target));
                module_roots.insert(target);
            }
        }
    }
    let roots: Vec<_> = references
        .iter()
        .filter(|(file, _)| !imported.contains(file) || module_roots.contains(file))
        .map(|(file, _)| file)
        .collect();
    let roots: Vec<_> = roots
        .iter()
        .copied()
        .chain(
            references
                .iter()
                .filter(|(file, _)| !roots.contains(file))
                .map(|(file, _)| file),
        )
        .collect();
    let mut reached = std::collections::HashSet::new();
    for root in roots {
        if reached.contains(&root) && imported.contains(&root) && !module_roots.contains(&root) {
            continue;
        }
        let visible = scope(root, &imports);
        reached.extend(visible.keys().copied());
        for &file in visible.keys() {
            let Some(reference) = references.get(file) else {
                continue;
            };
            for (kind, name) in &reference.imports {
                if kind == "recipe"
                    && let Some(target) =
                        recipe_target(name, &visible, &imports, &modules, references)
                {
                    edges.push((file, target));
                }
            }
        }
    }
    local::finish(edges)
}

struct Header {
    range: std::ops::Range<usize>,
    name: String,
    dependencies: Vec<String>,
}

// The pinned grammar predates namespace-qualified dependencies. Recover only
// literal, parameterless headers, never recipe commands or multiline strings.
fn headers(root: ts::Node<'_>, source: &[u8]) -> Vec<Header> {
    static HEADER: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
        regex::Regex::new(
        r"(?m)^@?([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:[ \t]*((?:[A-Za-z_][A-Za-z0-9_-]*(?:::[A-Za-z_][A-Za-z0-9_-]*)*(?:[ \t]+|$))*)[ \t]*(?:#[^\r\n]*)?\r?$"
    ).unwrap()
    });
    let Ok(raw) = std::str::from_utf8(source) else {
        return Vec::new();
    };
    HEADER
        .captures_iter(raw)
        .filter_map(|captures| {
            let matched = captures.get(0)?;
            let mut node =
                root.descendant_for_byte_range(matched.start(), matched.end().saturating_sub(1));
            while let Some(current) = node {
                if matches!(
                    current.kind(),
                    "string" | "comment" | "recipe_body" | "recipe_line" | "external_command"
                ) {
                    return None;
                }
                node = current.parent();
            }
            Some(Header {
                range: matched.range(),
                name: captures[1].into(),
                dependencies: captures[2].split_whitespace().map(str::to_owned).collect(),
            })
        })
        .collect()
}
