//! Resolve captured references to indexed local files.

use std::collections::HashMap;
use std::path::Path;

use la_arena::ArenaMap;

use super::dependencies::Dependencies;
use super::manifest::GoPackage;
use crate::index::{FileId, Index, PackageId};

/// Resolves imports and same-package file dependencies across local modules.
///
/// Includes possible local build contexts without evaluating build tags.
/// Returns sorted, deduplicated edges.
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, GoPackage>,
    dependencies: &ArenaMap<FileId, Dependencies>,
) -> Vec<(FileId, FileId)> {
    let mut contexts: HashMap<_, Vec<_>> = HashMap::new();

    // Replacement modules use the main module's build list, not their own replacements.
    for (owner, package) in packages.iter() {
        let mut members: Vec<_> = package.modules.iter().map(|(_, member)| *member).collect();
        members.sort_unstable();
        members.dedup();

        for member in members {
            contexts.entry(member).or_default().push(owner);
        }
    }

    let mut directories: HashMap<_, Vec<_>> = HashMap::new();

    for (file, dependency) in dependencies.iter() {
        let source = &index.files[file];

        if dependency.package.is_some() && !ignored_file(&source.path) {
            directories
                .entry((source.package_id, source.path.parent().unwrap()))
                .or_default()
                .push(file);
        }
    }

    let mut edges = Vec::new();

    for (file, dependency) in dependencies.iter() {
        let source = &index.files[file];

        if ignored_file(&source.path) {
            continue;
        }

        let directory = source.path.parent().unwrap();
        let is_test = test_file(&source.path);

        if let Some(peers) = directories.get(&(source.package_id, directory)) {
            for &peer in peers {
                let same_package = dependency.package == dependencies[peer].package;
                let internal_package = is_test
                    && !test_file(&index.files[peer].path)
                    && dependency
                        .package
                        .as_deref()
                        .and_then(|name| name.strip_suffix("_test"))
                        == dependencies[peer].package.as_deref();

                if peer != file
                    && (same_package || internal_package)
                    && (is_test || !test_file(&index.files[peer].path))
                {
                    edges.push((file, peer));
                }
            }
        }

        let Some(contexts) = contexts.get(&source.package_id) else {
            continue;
        };

        for &context in contexts {
            let package = &packages[context];

            for import in &dependency.imports {
                let Some((module, target)) = package
                    .modules
                    .iter()
                    .filter(|(module, _)| {
                        import == module
                            || import
                                .strip_prefix(module.as_str())
                                .is_some_and(|suffix| suffix.starts_with('/'))
                    })
                    .max_by_key(|(module, _)| module.len())
                else {
                    continue;
                };
                let suffix = import.strip_prefix(module).unwrap();
                let suffix = suffix.strip_prefix('/').unwrap_or(suffix);

                if !suffix.is_empty()
                    && suffix
                        .split('/')
                        .any(|component| matches!(component, "" | "." | ".."))
                    || suffix.contains('\\')
                {
                    continue;
                }

                let directory = index.packages[*target].root.join(suffix);

                if let Some(targets) = directories.get(&(*target, directory.as_path())) {
                    for &target in targets {
                        if target != file
                            && !test_file(&index.files[target].path)
                            && dependencies[target].package.as_deref() != Some("main")
                        {
                            edges.push((file, target));
                        }
                    }
                }
            }
        }
    }

    edges.sort_unstable();
    edges.dedup();
    edges
}

fn ignored_file(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.starts_with(['_', '.']))
}

fn test_file(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.ends_with("_test.go"))
}

/// Matches embed files and recursively included directories without accessing outside the index.
pub(super) fn embeds(
    index: &Index,
    repository: &crate::repo::Repository,
    dependencies: &ArenaMap<FileId, Dependencies>,
) -> Vec<(FileId, FileId)> {
    let mut edges = Vec::new();
    for (file, dependencies) in dependencies.iter() {
        let directory = index.files[file].path.parent().unwrap();
        for pattern in &dependencies.embeds {
            let all = pattern.starts_with("all:");
            let pattern = pattern.strip_prefix("all:").unwrap_or(pattern);
            if pattern
                .split('/')
                .any(|part| matches!(part, "" | "." | ".."))
                || pattern.contains(['\\', ':'])
            {
                continue;
            }
            let Some(glob) = crate::languages::local::path_glob(Path::new(""), pattern) else {
                continue;
            };
            for (target, source) in index.files.iter() {
                if repository.sources.get(target).is_none() {
                    continue;
                }
                let Ok(relative) = source.path.strip_prefix(directory) else {
                    continue;
                };
                if !all
                    && relative.components().any(|part| {
                        part.as_os_str()
                            .to_str()
                            .is_some_and(|part| part.starts_with(['.', '_']))
                    })
                {
                    continue;
                }
                let nested_module = source
                    .path
                    .parent()
                    .unwrap()
                    .ancestors()
                    .take_while(|parent| *parent != directory)
                    .any(|parent| {
                        index
                            .files
                            .iter()
                            .any(|(_, source)| source.path == parent.join("go.mod"))
                    });
                if nested_module {
                    continue;
                }
                if glob.is_match(relative)
                    || relative
                        .ancestors()
                        .skip(1)
                        .any(|ancestor| glob.is_match(ancestor))
                {
                    edges.push((file, target));
                }
            }
        }
    }
    edges
}
