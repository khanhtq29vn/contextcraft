//! Resolve captured references to indexed local files.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use la_arena::ArenaMap;

use super::dependencies::{Import, ImportKind};
use super::manifest::json_config;
use crate::index::{FileId, Index};
use crate::languages::local;
use crate::package::local_path;
use crate::repo::Repository;
use serde_json::Value;

/// Resolves relative script imports to readable scripts, components, JSON, and stylesheets.
///
/// Resolves declared local workspace packages, package exports, and static JSONC
/// path aliases. Unknown runtime/bundler conditions remain unresolved.
pub fn resolve(
    index: &Index,
    repository: &Repository,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)> {
    resolve_components(index, repository, imports, &HashSet::new())
}

pub(in crate::languages) fn resolve_components(
    index: &Index,
    repository: &Repository,
    imports: &ArenaMap<FileId, Vec<Import>>,
    typed_components: &HashSet<FileId>,
) -> Vec<(FileId, FileId)> {
    let files: HashMap<_, _> = index
        .files
        .iter()
        .filter(|(id, file)| {
            repository.sources.get(*id).is_some()
                && (matches!(
                    file.language,
                    Some("javascript" | "typescript" | "tsx" | "vue" | "svelte" | "css" | "scss")
                ) || file
                    .path
                    .extension()
                    .is_some_and(|extension| extension == "json"))
        })
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    let all_files = local::readable_files(index, repository);
    let find =
        |path: &Path| local_path(index, path).and_then(|path| files.get(path.as_path()).copied());
    let mut edges = Vec::new();

    for (file, imports) in imports.iter() {
        let source = &index.files[file];
        let typed = matches!(source.language, Some("typescript" | "tsx"))
            || typed_components.contains(&file);
        let probe_javascript = matches!(source.language, Some("vue" | "svelte"))
            || source
                .path
                .extension()
                .is_some_and(|extension| extension == "jsx");

        let config = source
            .path
            .parent()
            .unwrap()
            .ancestors()
            .find_map(|directory| {
                ["tsconfig.json", "jsconfig.json"].iter().find_map(|name| {
                    let path = directory.join(name);
                    let id = local::find(index, &all_files, &path)?;
                    repository.sources.get(id)?;
                    load_config(index, repository, &path, &mut Vec::new())
                })
            });
        if let Some(config_file) = config.as_ref().and_then(|config| config.file) {
            edges.push((file, config_file));
        }
        for import in imports {
            if import.path.contains(['\\', '\0']) {
                continue;
            }
            if !(import.path.starts_with("./") || import.path.starts_with("../")) {
                let mut targets = Vec::new();
                if let Some(config) = &config {
                    let mut aliases: Vec<_> = config
                        .paths
                        .iter()
                        .filter_map(|(pattern, replacements)| {
                            let capture = if let Some((prefix, suffix)) = pattern.split_once('*') {
                                import.path.strip_prefix(prefix)?.strip_suffix(suffix)?
                            } else if pattern == &import.path {
                                ""
                            } else {
                                return None;
                            };
                            Some((pattern, replacements, capture))
                        })
                        .collect();
                    aliases.sort_by(|a, b| {
                        let rank = |pattern: &str| {
                            (
                                !pattern.contains('*'),
                                pattern.split('*').next().unwrap().len(),
                                pattern.len(),
                            )
                        };
                        rank(b.0).cmp(&rank(a.0))
                    });
                    if let Some((_, replacements, capture)) = aliases.first() {
                        for replacement in *replacements {
                            if let Some(target) = probe(
                                index,
                                &files,
                                &config.paths_base.join(replacement.replace('*', capture)),
                                typed,
                                true,
                            ) {
                                targets.push(target);
                                break;
                            }
                        }
                    } else if let Some(base) = &config.base_url
                        && let Some(target) =
                            probe(index, &files, &base.join(&import.path), typed, true)
                    {
                        targets.push(target);
                    }
                }
                if targets.is_empty() {
                    let package = &index.packages[source.package_id];
                    let mut candidates: Vec<_> = package
                        .dependencies
                        .iter()
                        .map(|dependency| (dependency.alias.as_str(), dependency.package))
                        .collect();
                    if let Some(name) = package.name.as_deref() {
                        candidates.push((name, source.package_id));
                    }
                    candidates.sort_by_key(|(name, _)| std::cmp::Reverse(name.len()));
                    if let Some((alias, package)) = candidates.into_iter().find(|(alias, _)| {
                        import.path == *alias
                            || import
                                .path
                                .strip_prefix(alias)
                                .is_some_and(|suffix| suffix.starts_with('/'))
                    }) {
                        let package = &index.packages[package];
                        let subpath = import
                            .path
                            .strip_prefix(alias)
                            .unwrap()
                            .trim_start_matches('/');
                        if subpath.split('/').any(|part| matches!(part, ".." | ".")) {
                            continue;
                        }
                        let manifest = package.root.join("package.json");
                        if let Some(id) = local::find(index, &all_files, &manifest)
                            && let Some(source) = repository.sources.get(id)
                            && let Ok(document) = serde_json::from_slice::<Value>(&source.bytes)
                        {
                            let entry = package_entry(&document, subpath, typed, import.kind);
                            for entry in entry {
                                if let Some(target) =
                                    probe(index, &files, &package.root.join(entry), typed, true)
                                    && index.files[target].path.starts_with(&package.root)
                                {
                                    targets.push(target);
                                    break;
                                }
                            }
                        }
                    }
                }
                edges.extend(
                    targets
                        .into_iter()
                        .filter(|target| *target != file)
                        .map(|target| (file, target)),
                );
                continue;
            }

            let path = source.path.parent().unwrap().join(&import.path);
            let extension = path.extension().and_then(|extension| extension.to_str());
            let substitutions: &[&str] = if typed {
                match extension {
                    Some("js") => &["ts", "tsx", "d.ts", "js"],
                    Some("jsx") => &["tsx", "d.ts", "jsx"],
                    Some("mjs") => &["mts", "d.mts", "mjs"],
                    Some("cjs") => &["cts", "d.cts", "cjs"],
                    _ => &[],
                }
            } else {
                &[]
            };
            let target = if substitutions.is_empty() {
                find(&path)
            } else {
                substitutions
                    .iter()
                    .find_map(|extension| find(&path.with_extension(extension)))
            };
            let target = target.or_else(|| {
                // Plain JS uses explicit ESM paths; TS, JSX, and component scripts
                // also probe extensions without inferring bundler-specific aliases.
                let extensions: &[&str] = if typed {
                    &["ts", "tsx", "d.ts", "js", "jsx", "json"]
                } else if probe_javascript {
                    &["js", "jsx", "json"]
                } else if import.kind == ImportKind::Require {
                    &["js", "json"]
                } else {
                    return None;
                };

                if typed && extension.is_some() {
                    return None;
                }

                extensions
                    .iter()
                    .map(|extension| append_extension(&path, extension))
                    .chain(
                        extensions
                            .iter()
                            .map(|extension| path.join(format!("index.{extension}"))),
                    )
                    .find_map(|path| find(&path))
            });

            if let Some(target) = target
                && target != file
            {
                edges.push((file, target));
            }
        }
    }

    for (&path, &file) in &all_files {
        if !path
            .file_name()
            .is_some_and(|name| name == "tsconfig.json" || name == "jsconfig.json")
        {
            continue;
        }
        let Some(source) = repository.sources.get(file) else {
            continue;
        };
        let Some(document) = json_config(&source.bytes) else {
            continue;
        };
        let references = document
            .get("references")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|value| value.get("path").and_then(Value::as_str));
        let extends = document
            .get("extends")
            .into_iter()
            .flat_map(|value| {
                value
                    .as_array()
                    .map_or_else(|| vec![value], |values| values.iter().collect())
            })
            .filter_map(Value::as_str)
            .filter(|path| path.starts_with("./") || path.starts_with("../"));
        for reference in references.chain(extends) {
            let target = path.parent().unwrap().join(reference);
            let candidates = [
                target.clone(),
                target.with_extension("json"),
                target.join("tsconfig.json"),
            ];
            if let Some(target) = candidates
                .iter()
                .find_map(|path| local::find(index, &all_files, path))
            {
                edges.push((file, target));
            }
        }
    }
    edges.sort_unstable();
    edges.dedup();
    edges
}

fn append_extension(path: &Path, extension: &str) -> PathBuf {
    let mut path = path.as_os_str().to_os_string();
    path.push(".");
    path.push(extension);
    path.into()
}

#[derive(Default)]
struct Config {
    file: Option<FileId>,
    base_url: Option<PathBuf>,
    paths_base: PathBuf,
    paths: HashMap<String, Vec<String>>,
}

fn load_config(
    index: &Index,
    repository: &Repository,
    path: &Path,
    seen: &mut Vec<PathBuf>,
) -> Option<Config> {
    let path = local_path(index, path)?;
    if seen.contains(&path) {
        return None;
    }
    seen.push(path.clone());
    let files = local::readable_files(index, repository);
    let id = local::find(index, &files, &path)?;
    let document = json_config(&repository.sources.get(id)?.bytes)?;
    let directory = path.parent()?;
    let mut config = Config::default();
    for extends in document
        .get("extends")
        .into_iter()
        .flat_map(|value| {
            value
                .as_array()
                .map_or_else(|| vec![value], |values| values.iter().collect())
        })
        .filter_map(Value::as_str)
    {
        if !(extends.starts_with("./") || extends.starts_with("../")) {
            continue;
        }
        let mut parent = directory.join(extends);
        if parent.extension().is_none() {
            parent.set_extension("json");
        }
        if let Some(parent) = load_config(index, repository, &parent, seen) {
            config = parent;
        }
    }
    if let Some(options) = document.get("compilerOptions") {
        if let Some(base) = options.get("baseUrl").and_then(Value::as_str) {
            config.base_url = Some(directory.join(base));
        }
        if let Some(paths) = options.get("paths").and_then(Value::as_object) {
            config.paths_base = config
                .base_url
                .clone()
                .unwrap_or_else(|| directory.to_path_buf());
            config.paths = paths
                .iter()
                .map(|(pattern, paths)| {
                    (
                        pattern.clone(),
                        paths
                            .as_array()
                            .into_iter()
                            .flatten()
                            .filter_map(Value::as_str)
                            .map(str::to_owned)
                            .collect(),
                    )
                })
                .collect();
        }
    }
    config.file = Some(id);
    seen.pop();
    Some(config)
}

fn probe(
    index: &Index,
    files: &HashMap<&Path, FileId>,
    path: &Path,
    typed: bool,
    extensions: bool,
) -> Option<FileId> {
    let find = |path: &Path| local::find(index, files, path);
    if typed {
        let replacements: &[&str] = match path.extension().and_then(|value| value.to_str()) {
            Some("js") => &["ts", "tsx", "d.ts", "js"],
            Some("jsx") => &["tsx", "d.ts", "jsx"],
            Some("mjs") => &["mts", "d.mts", "mjs"],
            Some("cjs") => &["cts", "d.cts", "cjs"],
            _ => &[],
        };
        if !replacements.is_empty() {
            return replacements
                .iter()
                .find_map(|extension| find(&path.with_extension(extension)));
        }
    }
    find(path).or_else(|| {
        if !extensions || path.extension().is_some() {
            return None;
        }
        let extensions: &[&str] = if typed {
            &["ts", "tsx", "d.ts", "mts", "cts", "js", "jsx", "json"]
        } else {
            &["js", "cjs", "mjs", "json"]
        };
        extensions
            .iter()
            .map(|extension| append_extension(path, extension))
            .chain(
                extensions
                    .iter()
                    .map(|extension| path.join(format!("index.{extension}"))),
            )
            .find_map(|path| find(&path))
    })
}

fn package_entry(document: &Value, subpath: &str, typed: bool, kind: ImportKind) -> Vec<String> {
    fn target(value: &Value, typed: bool, kind: ImportKind) -> Vec<String> {
        if let Some(path) = value.as_str() {
            return if path.starts_with("./")
                && !path
                    .split('/')
                    .any(|part| matches!(part, ".." | "node_modules"))
            {
                vec![path.to_owned()]
            } else {
                Vec::new()
            };
        }
        if let Some(values) = value.as_array() {
            return values
                .iter()
                .flat_map(|value| target(value, typed, kind))
                .collect();
        }
        if let Some(values) = value.as_object() {
            for (condition, value) in values {
                if condition == "default"
                    || condition == "node"
                    || (condition == "types" && typed)
                    || (condition == "import" && kind == ImportKind::Module)
                    || (condition == "require" && kind == ImportKind::Require)
                {
                    return target(value, typed, kind);
                }
            }
        }
        Vec::new()
    }
    if let Some(exports) = document.get("exports") {
        let key = if subpath.is_empty() {
            ".".into()
        } else {
            format!("./{subpath}")
        };
        if let Some(object) = exports.as_object()
            && object.keys().any(|key| key.starts_with('.'))
        {
            if let Some(value) = object.get(&key) {
                return target(value, typed, kind);
            }
            let mut patterns: Vec<_> = object
                .iter()
                .filter_map(|(pattern, value)| {
                    let (prefix, suffix) = pattern.split_once('*')?;
                    let capture = key.strip_prefix(prefix)?.strip_suffix(suffix)?;
                    Some((prefix.len(), suffix.len(), capture, value))
                })
                .collect();
            patterns.sort_by_key(|(prefix, suffix, _, _)| std::cmp::Reverse((*prefix, *suffix)));
            if let Some((_, _, capture, value)) = patterns.first() {
                return target(value, typed, kind)
                    .into_iter()
                    .map(|path| path.replace('*', capture))
                    .collect();
            }
            return Vec::new();
        }
        return if subpath.is_empty() {
            target(exports, typed, kind)
        } else {
            Vec::new()
        };
    }
    if !subpath.is_empty() {
        return vec![subpath.to_owned()];
    }
    let fields: &[&str] = if typed {
        &["types", "typings", "module", "main"]
    } else if kind == ImportKind::Module {
        &["module", "main"]
    } else {
        &["main"]
    };
    fields
        .iter()
        .filter_map(|field| {
            document
                .get(*field)
                .and_then(Value::as_str)
                .map(str::to_owned)
        })
        .chain(std::iter::once("index".into()))
        .collect()
}
