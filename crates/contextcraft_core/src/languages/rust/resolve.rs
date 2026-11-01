//! Resolve captured references to indexed local files.

use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

use la_arena::ArenaMap;

use super::dependencies::{Import, RustDependencies};
use super::manifest::{DependencyKind, RustPackage, TargetKind};
use crate::index::{FileId, Index, PackageId};
use crate::package::local_path;

type ModuleKey = (FileId, Vec<String>);
type ModuleLookup<'a> = HashMap<FileId, HashMap<&'a [String], Option<FileId>>>;
type Bindings<'a> = HashMap<(FileId, &'a [String]), HashMap<&'a str, HashSet<ModuleKey>>>;

struct Module {
    key: ModuleKey,
    file: FileId,
    package: PackageId,
    kind: TargetKind,
    test_only: bool,
    context: Vec<String>,
    directory: PathBuf,
    attribute_directory: PathBuf,
    ancestors: Vec<FileId>,
}

/// Resolves module declarations and imports within discovered Cargo targets.
///
/// Resolves module aliases to a fixed point. Ambiguous module paths are not
/// assigned an arbitrary target. Returned edges may contain duplicates.
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, RustPackage>,
    dependencies: &ArenaMap<FileId, RustDependencies>,
) -> Vec<(FileId, FileId)> {
    let (modules, mut edges) = discover_modules(index, packages, dependencies);

    let mut lookup = ModuleLookup::new();

    for module in &modules {
        lookup
            .entry(module.key.0)
            .or_default()
            .entry(module.key.1.as_slice())
            .and_modify(|file| {
                if *file != Some(module.file) {
                    *file = None;
                }
            })
            .or_insert(Some(module.file));
    }

    let mut imports = Vec::new();

    for module in &modules {
        if let Some(dependencies) = dependencies.get(module.file) {
            for import in &dependencies.imports {
                if import.context == module.context {
                    imports.push((module, import));
                }
            }
        }
    }

    let mut bindings = HashMap::new();

    // Resolve module aliases to a fixed point, independently of declaration order.
    loop {
        let mut changed = false;

        for &(module, import) in &imports {
            if import.glob || !import.module_level {
                continue;
            }

            let Some((target, true)) = resolve_import(packages, module, import, &lookup, &bindings)
            else {
                continue;
            };

            if unique_file(&target, &lookup).is_none() {
                continue;
            }

            let alias = import
                .alias
                .as_ref()
                .or_else(|| import.path.last())
                .unwrap();

            if alias == "_" {
                continue;
            }

            let scope = (module.key.0, module.key.1.as_slice());
            changed |= bindings
                .entry(scope)
                .or_default()
                .entry(alias.as_str())
                .or_default()
                .insert(target);
        }

        if !changed {
            break;
        }
    }

    for (module, import) in imports {
        if let Some((target, _)) = resolve_import(packages, module, import, &lookup, &bindings)
            && let Some(file) = unique_file(&target, &lookup)
            && file != module.file
        {
            edges.push((module.file, file));
        }
    }

    edges
}

fn discover_modules(
    index: &Index,
    packages: &ArenaMap<PackageId, RustPackage>,
    dependencies: &ArenaMap<FileId, RustDependencies>,
) -> (Vec<Module>, Vec<(FileId, FileId)>) {
    let mut edges = Vec::new();
    let files: HashMap<_, _> = index
        .files
        .iter()
        .filter(|(_, file)| file.language == Some("rust"))
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();

    let mut modules = Vec::new();

    for (package, rust) in packages.iter() {
        for target in &rust.targets {
            let directory = index.files[target.root]
                .path
                .parent()
                .unwrap()
                .to_path_buf();

            modules.push(Module {
                key: (target.root, Vec::new()),
                file: target.root,
                package,
                kind: target.kind,
                test_only: false,
                context: Vec::new(),
                attribute_directory: directory.clone(),
                directory,
                ancestors: vec![target.root],
            });
        }
    }

    let mut cursor = 0;

    while cursor < modules.len() {
        let module = &modules[cursor];
        let mut children = Vec::new();

        if let Some(dependencies) = dependencies.get(module.file) {
            for declaration in &dependencies.modules {
                if declaration.context != module.context || declaration.unresolved_path {
                    continue;
                }

                let mut path = module.key.1.clone();
                path.push(declaration.name.clone());

                let child = if declaration.inline {
                    let directory = declaration
                        .path_override
                        .as_ref()
                        .map(|path| module.attribute_directory.join(path))
                        .unwrap_or_else(|| module.directory.join(&declaration.name));
                    let mut context = module.context.clone();
                    context.push(declaration.name.clone());

                    Module {
                        key: (module.key.0, path),
                        file: module.file,
                        package: module.package,
                        kind: module.kind,
                        test_only: module.test_only || declaration.test_only,
                        context,
                        attribute_directory: directory.clone(),
                        directory,
                        ancestors: module.ancestors.clone(),
                    }
                } else {
                    let candidates = if let Some(path) = &declaration.path_override {
                        [Some(module.attribute_directory.join(path)), None]
                    } else {
                        [
                            Some(module.directory.join(format!("{}.rs", declaration.name))),
                            Some(module.directory.join(&declaration.name).join("mod.rs")),
                        ]
                    };

                    let mut candidates = candidates
                        .iter()
                        .flatten()
                        .filter_map(|path| local_path(index, path))
                        .filter_map(|path| files.get(path.as_path()).copied());
                    let Some(file) = candidates.next() else {
                        continue;
                    };

                    if candidates.next().is_some() {
                        continue;
                    }

                    if module.ancestors.contains(&file) {
                        continue;
                    }

                    let file_path = &index.files[file].path;
                    let attribute_directory = file_path.parent().unwrap().to_path_buf();
                    let directory = if file_path.file_name().is_some_and(|name| name == "mod.rs") {
                        attribute_directory.clone()
                    } else {
                        attribute_directory.join(file_path.file_stem().unwrap())
                    };

                    let mut ancestors = module.ancestors.clone();
                    ancestors.push(file);
                    edges.push((module.file, file));

                    Module {
                        key: (module.key.0, path),
                        file,
                        package: module.package,
                        kind: module.kind,
                        test_only: module.test_only || declaration.test_only,
                        context: Vec::new(),
                        directory,
                        attribute_directory,
                        ancestors,
                    }
                };

                children.push(child);
            }
        }

        modules.extend(children);
        cursor += 1;
    }

    (modules, edges)
}

fn unique_file(key: &ModuleKey, lookup: &ModuleLookup<'_>) -> Option<FileId> {
    let modules = lookup.get(&key.0)?;

    // None marks a cfg-dependent module path with multiple possible files.
    for length in 0..=key.1.len() {
        if modules.get(&key.1[..length]).is_some_and(Option::is_none) {
            return None;
        }
    }

    modules.get(key.1.as_slice()).copied().flatten()
}

fn resolve_import(
    packages: &ArenaMap<PackageId, RustPackage>,
    module: &Module,
    import: &Import,
    lookup: &ModuleLookup<'_>,
    bindings: &Bindings<'_>,
) -> Option<(ModuleKey, bool)> {
    let (first, rest) = import.path.split_first()?;
    let rust = &packages[module.package];
    let mut consumed = 1;
    let mut key = match first.as_str() {
        "crate" => (module.key.0, Vec::new()),
        "self" => {
            if import.external {
                (module.key.0, Vec::new())
            } else {
                module.key.clone()
            }
        }

        "super" => {
            let mut key = module.key.clone();
            key.1.pop()?;

            while import
                .path
                .get(consumed)
                .is_some_and(|part| part == "super")
            {
                key.1.pop()?;
                consumed += 1;
            }

            key
        }

        name => {
            let base = if rust.edition == "2015" {
                &[][..]
            } else {
                module.key.1.as_slice()
            };
            let mut local = (module.key.0, base.to_vec());
            local.1.push(name.to_owned());

            if !import.external
                && (!import.absolute || rust.edition == "2015")
                && lookup
                    .get(&local.0)
                    .is_some_and(|modules| modules.contains_key(local.1.as_slice()))
            {
                local
            } else if (!import.absolute || rust.edition == "2015")
                && !import.external
                && let Some(targets) = bindings
                    .get(&(module.key.0, base))
                    .and_then(|aliases| aliases.get(name))
            {
                if targets.len() != 1 {
                    return None;
                }

                targets.iter().next()?.clone()
            } else {
                if rust.edition == "2015" && !import.external {
                    return None;
                }

                let mut root = if module.kind != TargetKind::Build && rust.crate_name == name {
                    rust.library
                } else {
                    None
                };

                for dependency in &rust.dependencies {
                    let visible = match module.kind {
                        TargetKind::Build => dependency.kind == DependencyKind::Build,
                        TargetKind::Test | TargetKind::Example | TargetKind::Bench => {
                            dependency.kind != DependencyKind::Build
                        }

                        _ => {
                            dependency.kind == DependencyKind::Normal
                                || (module.test_only || import.test_only)
                                    && dependency.kind == DependencyKind::Dev
                        }
                    };

                    if visible
                        && dependency.alias == name
                        && let Some(library) = packages
                            .get(dependency.package)
                            .and_then(|package| package.library)
                    {
                        if root.is_some_and(|root| root != library) {
                            return None;
                        }
                        root = Some(library);
                    }
                }

                (root?, Vec::new())
            }
        }
    };

    let remaining = if consumed == 1 {
        rest
    } else {
        &import.path[consumed..]
    };

    for (position, segment) in remaining.iter().enumerate() {
        key.1.push(segment.clone());

        if lookup
            .get(&key.0)
            .is_some_and(|modules| modules.contains_key(key.1.as_slice()))
        {
            continue;
        }

        key.1.pop();

        if key.0 == module.key.0
            && let Some(targets) = bindings
                .get(&(key.0, key.1.as_slice()))
                .and_then(|aliases| aliases.get(segment.as_str()))
        {
            if targets.len() != 1 {
                return None;
            }
            key = targets.iter().next()?.clone();
        } else {
            // Only the final segment may be a symbol defined by the module file.
            return (position + 1 == remaining.len() && !import.glob).then_some((key, false));
        }
    }

    Some((key, true))
}
