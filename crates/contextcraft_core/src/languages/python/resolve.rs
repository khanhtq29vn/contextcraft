//! Resolve captured references to indexed local files.

use std::collections::{HashMap, HashSet};

use la_arena::ArenaMap;

use super::dependencies::Import;
use super::manifest::{PythonPackage, SourceRoot};
use crate::index::{FileId, Index, PackageId};

#[derive(Clone, Copy)]
struct Module {
    file: Option<FileId>,
    is_package: bool,
    rank: usize,
}

struct ModuleContext<'a> {
    name: Vec<&'a str>,
    is_package: bool,
}

struct ModuleIndex<'a> {
    roots: Vec<(PackageId, &'a SourceRoot)>,
    modules: Vec<HashMap<Vec<&'a str>, Module>>,
    contexts: HashMap<FileId, Vec<ModuleContext<'a>>>,
}

struct ResolvedModule {
    files: Vec<FileId>,
    is_package: bool,
}

/// Resolves imports through visible local packages and configured source roots.
///
/// Includes package initializers and handles namespace packages. Ambiguous
/// external package ownership is not resolved. Returns sorted, deduplicated edges.
pub fn resolve(
    index: &Index,
    packages: &ArenaMap<PackageId, PythonPackage>,
    imports: &ArenaMap<FileId, Vec<Import>>,
) -> Vec<(FileId, FileId)> {
    let modules = ModuleIndex::new(index, packages);
    let mut visibility = HashMap::new();

    for (id, _) in packages.iter() {
        let mut visible = HashSet::from([id]);
        let mut pending = vec![id];

        while let Some(package) = pending.pop() {
            for dependency in &index.packages[package].dependencies {
                if packages.get(dependency.package).is_some() && visible.insert(dependency.package)
                {
                    pending.push(dependency.package);
                }
            }
        }

        let roots: Vec<_> = modules
            .roots
            .iter()
            .enumerate()
            .filter_map(|(root, (owner, _))| visible.contains(owner).then_some(root))
            .collect();
        visibility.insert(id, roots);
    }

    let mut edges = Vec::new();

    for (file, imports) in imports.iter() {
        let owner = index.files[file].package_id;
        let Some(visible) = visibility.get(&owner) else {
            continue;
        };

        for import in imports {
            for mut name in modules.import_names(file, import) {
                let Some(base) = modules.find(&name, visible, owner) else {
                    continue;
                };

                let mut targets = base.files;

                if import.from && !import.wildcard && base.is_package {
                    let prefix_len = name.len();

                    for imported in &import.names {
                        name.truncate(prefix_len);
                        name.extend(imported.path.iter().map(String::as_str));

                        if let Some(resolved) = modules.find(&name, visible, owner) {
                            targets.extend(resolved.files);
                        }
                    }
                }

                for target in targets {
                    if target != file {
                        edges.push((file, target));
                    }
                }
            }
        }
    }

    edges.sort_unstable();
    edges.dedup();
    edges
}

impl<'a> ModuleIndex<'a> {
    fn new(index: &'a Index, packages: &'a ArenaMap<PackageId, PythonPackage>) -> Self {
        let roots: Vec<_> = packages
            .iter()
            .flat_map(|(id, package)| package.roots.iter().map(move |root| (id, root)))
            .collect();
        let mut package_roots: HashMap<_, Vec<_>> = HashMap::new();

        for (root, (owner, _)) in roots.iter().enumerate() {
            package_roots.entry(*owner).or_default().push(root);
        }

        let mut modules: Vec<HashMap<_, _>> = Vec::with_capacity(roots.len());
        modules.resize_with(roots.len(), HashMap::new);
        let mut contexts: HashMap<_, Vec<_>> = HashMap::new();

        for (file_id, file) in index.files.iter() {
            if file.language != Some("python") {
                continue;
            }

            let Some(root_ids) = package_roots.get(&file.package_id) else {
                continue;
            };
            let depth = root_ids
                .iter()
                .map(|&root| roots[root].1)
                .filter(|root| file.path.starts_with(&root.path))
                .map(|root| root.path.components().count())
                .max();

            'source_roots: for &root_id in root_ids {
                let root = roots[root_id].1;

                if Some(root.path.components().count()) != depth {
                    continue;
                }

                let Ok(relative) = file.path.strip_prefix(&root.path) else {
                    continue;
                };

                let Some(stem) = relative.file_stem().and_then(|stem| stem.to_str()) else {
                    continue;
                };

                let mut name: Vec<_> = root.prefix.iter().map(String::as_str).collect();
                let Some(parent) = relative.parent() else {
                    continue;
                };

                for component in parent {
                    let Some(component) = component.to_str() else {
                        continue 'source_roots;
                    };
                    name.push(component);
                }
                let is_package = stem == "__init__";

                if !is_package {
                    name.push(stem);
                }

                contexts.entry(file_id).or_default().push(ModuleContext {
                    name: name.clone(),
                    is_package,
                });

                for length in 1..=name.len() {
                    modules[root_id]
                        .entry(name[..length].to_vec())
                        .or_insert(Module {
                            file: None,
                            is_package: true,
                            rank: usize::MAX,
                        });
                }

                let extension = file.path.extension().and_then(|ext| ext.to_str());
                let rank = match (extension, is_package) {
                    (Some("py"), true) => 0,
                    (Some("pyw"), true) => 1,
                    (Some("py"), false) => 2,
                    (Some("pyw"), false) => 3,
                    (_, true) => 4,
                    (_, false) => 5,
                };

                let module = Module {
                    file: Some(file_id),
                    is_package,
                    rank,
                };

                let entry = modules[root_id].entry(name).or_insert(module);

                if rank < entry.rank {
                    *entry = module;
                }
            }
        }

        Self {
            roots,
            modules,
            contexts,
        }
    }

    fn import_names<'b>(
        &'b self,
        file: FileId,
        import: &'b Import,
    ) -> impl Iterator<Item = Vec<&'b str>> {
        let absolute =
            (import.level == 0).then(|| import.module.iter().map(String::as_str).collect());
        let relative = self
            .contexts
            .get(&file)
            .into_iter()
            .flatten()
            .filter_map(move |context| {
                if import.level == 0 {
                    return None;
                }

                let parent_len = context.name.len() - usize::from(!context.is_package);

                if import.level > parent_len {
                    return None;
                }

                let mut name = context.name[..parent_len - (import.level - 1)].to_vec();
                name.extend(import.module.iter().map(String::as_str));
                Some(name)
            });

        absolute.into_iter().chain(relative)
    }

    fn find(&self, name: &[&str], visible: &[usize], owner: PackageId) -> Option<ResolvedModule> {
        if name.is_empty() {
            return None;
        }

        let mut roots = visible.to_vec();
        let mut files = Vec::new();
        let mut is_package = true;

        for length in 1..=name.len() {
            let prefix = &name[..length];
            roots.retain(|&root| self.modules[root].contains_key(prefix));

            let mut regular = roots.iter().filter_map(|&root| {
                let module = self.modules[root].get(prefix)?;
                module.file.map(|_| (root, *module))
            });
            let selected = regular
                .clone()
                .find(|(root, _)| self.roots[*root].0 == owner)
                .or_else(|| regular.clone().next());

            if let Some((root, module)) = selected {
                let selected_owner = self.roots[root].0;

                if selected_owner != owner
                    && regular.any(|(candidate, _)| self.roots[candidate].0 != selected_owner)
                {
                    return None;
                }

                files.push(module.file?);
                is_package = module.is_package;

                // Explicit package-dir mappings can mount children outside the parent's directory.
                roots.retain(|&candidate| {
                    if candidate == root || !is_package {
                        return false;
                    }

                    let (candidate_owner, source) = &self.roots[candidate];
                    *candidate_owner == selected_owner
                        && source.prefix.len() > length
                        && source.prefix[..length]
                            .iter()
                            .map(String::as_str)
                            .eq(prefix.iter().copied())
                });
                roots.insert(0, root);
            } else {
                is_package = true;
            }

            if roots.is_empty() || !is_package && length < name.len() {
                return None;
            }
        }

        Some(ResolvedModule { files, is_package })
    }
}
