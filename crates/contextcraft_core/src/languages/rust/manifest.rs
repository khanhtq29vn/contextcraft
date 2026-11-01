//! Discover local package metadata and workspace relationships.

use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};

use globset::{GlobBuilder, GlobSet, GlobSetBuilder};
use la_arena::ArenaMap;
use toml::Value;

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::{Workspace, local_path, read_toml, relative_path};

/// Cargo package metadata needed for local module and import resolution.
#[derive(Debug)]
pub struct RustPackage {
    /// Declared Cargo package name.
    pub name: String,
    /// Library crate name with hyphens normalized to underscores.
    pub crate_name: String,
    /// Effective Rust edition, including workspace inheritance.
    pub edition: String,
    /// Indexed library entry file, if available.
    pub library: Option<FileId>,
    /// Indexed build targets, including tests, examples, and build scripts.
    pub targets: Vec<Target>,
    /// Local path dependencies across dependency kinds and target configurations.
    pub dependencies: Vec<LocalDependency>,
}

/// Cargo target category controlling dependency visibility.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TargetKind {
    /// Library entry point.
    Library,
    /// Executable entry point.
    Binary,
    /// Package build script.
    Build,
    /// Example program.
    Example,
    /// Integration test target.
    Test,
    /// Benchmark target.
    Bench,
}

/// An indexed Cargo target entry point and its build category.
#[derive(Debug)]
pub struct Target {
    /// Entry file ID in the associated index.
    pub root: FileId,
    /// Build category used for dependency visibility.
    pub kind: TargetKind,
}

/// Cargo dependency table category.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DependencyKind {
    /// Dependency from a `dependencies` table.
    Normal,
    /// Dependency from a `dev-dependencies` table.
    Dev,
    /// Dependency from a `build-dependencies` table.
    Build,
}

/// Resolved Cargo path dependency, retaining its visibility category.
#[derive(Debug)]
pub struct LocalDependency {
    /// Crate name used in imports, with hyphens normalized to underscores.
    pub alias: String,
    /// Indexed local dependency package.
    pub package: PackageId,
    /// Dependency table category controlling target visibility.
    pub kind: DependencyKind,
    /// Target selector from a target-specific table, if present.
    ///
    /// Retained as metadata rather than evaluated for the current host.
    pub target: Option<String>,
}

struct Document {
    root: PathBuf,
    value: Value,
}

/// Discovers Cargo targets, workspaces, and local path dependencies.
///
/// Oversized manifests are skipped according to the configured file size limit.
///
/// # Errors
///
/// Returns an error if manifests cannot be read or parsed, or workspace
/// membership and dependency configuration are invalid.
pub fn discover(
    index: &Index,
    config: &Config,
) -> Result<(ArenaMap<PackageId, RustPackage>, Vec<Workspace>), Error> {
    let mut documents = BTreeMap::new();

    for (id, package) in index.packages.iter() {
        if package.language != Some("rust") {
            continue;
        }

        let Some(manifest) = package.manifests.first() else {
            continue;
        };

        let Some(value) = read_toml(index, manifest, config)? else {
            continue;
        };

        documents.insert(
            id,
            Document {
                root: package.root.clone(),
                value,
            },
        );
    }

    let roots: HashMap<_, _> = documents
        .iter()
        .map(|(&id, doc)| (doc.root.as_path(), id))
        .collect();

    let (workspaces, owners) = discover_workspaces(index, &documents, &roots)?;

    let files: HashMap<_, _> = index
        .files
        .iter()
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();

    let mut packages = ArenaMap::new();

    for (&id, doc) in &documents {
        let Some(package) = doc.value.get("package") else {
            continue;
        };

        let Some(name) = package.get("name").and_then(Value::as_str) else {
            return Err(Error::Manifest {
                path: doc.root.join("Cargo.toml"),
                message: "missing package.name".into(),
            });
        };

        let edition = package
            .get("edition")
            .and_then(Value::as_str)
            .or_else(|| {
                package
                    .get("edition")?
                    .get("workspace")?
                    .as_bool()
                    .filter(|&v| v)?;

                documents
                    .get(owners.get(&id)?)?
                    .value
                    .get("workspace")?
                    .get("package")?
                    .get("edition")?
                    .as_str()
            })
            .unwrap_or("2015")
            .to_owned();
        let targets = targets(index, doc, name, &files);
        let library = targets
            .iter()
            .find(|target| target.kind == TargetKind::Library)
            .map(|target| target.root);
        let crate_name = doc
            .value
            .get("lib")
            .and_then(|lib| lib.get("name"))
            .and_then(Value::as_str)
            .unwrap_or(name)
            .replace('-', "_");
        let mut dependencies = Vec::new();

        for (alias, kind, target, dependency) in dependency_tables(&doc.value) {
            let (dependency, base) = inherited_dependency(
                alias,
                dependency,
                doc,
                owners.get(&id).and_then(|id| documents.get(id)),
            );
            let Some(path) = dependency.get("path").and_then(Value::as_str) else {
                continue;
            };

            let Some(root) = local_path(index, &base.join(path)) else {
                continue;
            };

            let Some(&target_package) = roots.get(root.as_path()) else {
                continue;
            };

            let expected_name = dependency
                .get("package")
                .and_then(Value::as_str)
                .unwrap_or(alias);

            if documents[&target_package]
                .value
                .get("package")
                .and_then(|p| p.get("name"))
                .and_then(Value::as_str)
                != Some(expected_name)
            {
                continue;
            }

            let crate_alias = if dependency.get("package").is_some() {
                alias
            } else {
                documents[&target_package]
                    .value
                    .get("lib")
                    .and_then(|lib| lib.get("name"))
                    .and_then(Value::as_str)
                    .unwrap_or(alias)
            };

            dependencies.push(LocalDependency {
                alias: crate_alias.replace('-', "_"),
                package: target_package,
                kind,
                target: target.map(str::to_owned),
            });
        }

        packages.insert(
            id,
            RustPackage {
                name: name.to_owned(),
                crate_name,
                edition,
                library,
                targets,
                dependencies,
            },
        );
    }

    Ok((packages, workspaces))
}

fn discover_workspaces(
    index: &Index,
    documents: &BTreeMap<PackageId, Document>,
    roots: &HashMap<&Path, PackageId>,
) -> Result<(Vec<Workspace>, HashMap<PackageId, PackageId>), Error> {
    let mut workspaces = Vec::new();
    let mut owners = HashMap::new();

    for (&id, doc) in documents {
        let Some(workspace) = doc.value.get("workspace") else {
            continue;
        };

        let members = patterns(workspace.get("members"), &doc.root)?;
        let excluded = patterns(workspace.get("exclude"), &doc.root)?;
        let mut member_ids = Vec::new();

        for (&candidate, member) in documents {
            if member.value.get("package").is_none() {
                continue;
            }

            let relative = relative_path(&doc.root, &member.root);
            let explicit = member
                .value
                .get("package")
                .and_then(|p| p.get("workspace"))
                .and_then(Value::as_str)
                .and_then(|path| local_path(index, &member.root.join(path)))
                .is_some_and(|path| path == doc.root);

            if candidate == id
                || explicit
                || (members.is_match(&relative) && !excluded.is_match(&relative))
            {
                if owners
                    .insert(candidate, id)
                    .is_some_and(|owner| owner != id)
                {
                    return Err(Error::Manifest {
                        path: member.root.join("Cargo.toml"),
                        message: "package belongs to multiple workspaces".into(),
                    });
                }

                member_ids.push(candidate);
            }
        }

        workspaces.push(Workspace {
            root: doc.root.clone(),
            language: "rust",
            members: member_ids,
        });
    }

    // Cargo also includes in-tree path dependencies of workspace members.
    for workspace in &mut workspaces {
        let owner = roots[workspace.root.as_path()];
        let workspace_value = &documents[&owner].value["workspace"];
        let excluded = patterns(workspace_value.get("exclude"), &workspace.root)?;
        let mut cursor = 0;

        while cursor < workspace.members.len() {
            let member = workspace.members[cursor];
            let doc = &documents[&member];

            for (alias, _, _, dependency) in dependency_tables(&doc.value) {
                let (dependency, base) = inherited_dependency(
                    alias,
                    dependency,
                    doc,
                    owners.get(&member).and_then(|id| documents.get(id)),
                );
                let Some(path) = dependency.get("path").and_then(Value::as_str) else {
                    continue;
                };

                let Some(root) = local_path(index, &base.join(path)) else {
                    continue;
                };

                let Some(&target) = roots.get(root.as_path()) else {
                    continue;
                };

                let Ok(relative) = root.strip_prefix(&workspace.root) else {
                    continue;
                };

                if documents[&target].value.get("package").is_none()
                    || excluded.is_match(relative)
                    || owners.get(&target).is_some_and(|&other| other != owner)
                    || documents[&target].value.get("workspace").is_some() && target != owner
                {
                    continue;
                }

                if !workspace.members.contains(&target) {
                    owners.insert(target, owner);
                    workspace.members.push(target);
                }
            }

            cursor += 1;
        }

        workspace.members.sort_unstable();
    }

    Ok((workspaces, owners))
}

fn patterns(value: Option<&Value>, root: &Path) -> Result<GlobSet, Error> {
    let mut builder = GlobSetBuilder::new();

    for pattern in value
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
    {
        builder.add(
            GlobBuilder::new(pattern.trim_start_matches("./").trim_end_matches('/'))
                .literal_separator(true)
                .build()
                .map_err(|error| Error::Manifest {
                    path: root.join("Cargo.toml"),
                    message: error.to_string(),
                })?,
        );
    }

    builder.build().map_err(|error| Error::Manifest {
        path: root.join("Cargo.toml"),
        message: error.to_string(),
    })
}

fn dependency_tables<'a>(
    value: &'a Value,
) -> Vec<(&'a str, DependencyKind, Option<&'a str>, &'a Value)> {
    let mut result = Vec::new();
    let mut collect = |table: &'a Value, target: Option<&'a str>| {
        for (key, kind) in [
            ("dependencies", DependencyKind::Normal),
            ("dev-dependencies", DependencyKind::Dev),
            ("build-dependencies", DependencyKind::Build),
        ] {
            if let Some(dependencies) = table.get(key).and_then(Value::as_table) {
                for (alias, dependency) in dependencies {
                    result.push((alias.as_str(), kind, target, dependency));
                }
            }
        }
    };

    collect(value, None);

    if let Some(targets) = value.get("target").and_then(Value::as_table) {
        for (target, table) in targets {
            collect(table, Some(target.as_str()));
        }
    }

    result
}

fn inherited_dependency<'a>(
    alias: &str,
    dependency: &'a Value,
    doc: &'a Document,
    workspace: Option<&'a Document>,
) -> (&'a Value, &'a Path) {
    if dependency.get("workspace").and_then(Value::as_bool) == Some(true)
        && let Some(workspace) = workspace
        && let Some(inherited) = workspace
            .value
            .get("workspace")
            .and_then(|w| w.get("dependencies"))
            .and_then(|d| d.get(alias))
    {
        return (inherited, &workspace.root);
    }

    (dependency, &doc.root)
}

fn targets(
    index: &Index,
    doc: &Document,
    name: &str,
    files: &HashMap<&Path, FileId>,
) -> Vec<Target> {
    let mut targets = Vec::new();
    let mut add = |path: PathBuf, kind| {
        if let Some(path) = local_path(index, &doc.root.join(path))
            && let Some(&root) = files.get(path.as_path())
            && index.files[root].language == Some("rust")
            && !targets
                .iter()
                .any(|target: &Target| target.root == root && target.kind == kind)
        {
            targets.push(Target { root, kind });
        }
    };

    let lib = doc.value.get("lib");

    if lib.is_some() || doc.value["package"].get("autolib").and_then(Value::as_bool) != Some(false)
    {
        add(
            lib.and_then(|v| v.get("path"))
                .and_then(Value::as_str)
                .unwrap_or("src/lib.rs")
                .into(),
            TargetKind::Library,
        );
    }

    let build = doc.value["package"].get("build");

    if build.and_then(Value::as_bool) != Some(false) {
        add(
            build.and_then(Value::as_str).unwrap_or("build.rs").into(),
            TargetKind::Build,
        );
    }

    for (key, dir, kind) in [
        ("bin", "src/bin", TargetKind::Binary),
        ("example", "examples", TargetKind::Example),
        ("test", "tests", TargetKind::Test),
        ("bench", "benches", TargetKind::Bench),
    ] {
        let explicit = doc
            .value
            .get(key)
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[]);
        let explicit_names: Vec<_> = explicit
            .iter()
            .filter_map(|v| v.get("name").and_then(Value::as_str))
            .collect();

        for target in explicit {
            if let Some(path) = target.get("path").and_then(Value::as_str) {
                add(path.into(), kind);
            } else if let Some(target_name) = target.get("name").and_then(Value::as_str) {
                if kind == TargetKind::Binary
                    && target_name == name
                    && files.contains_key(doc.root.join("src/main.rs").as_path())
                {
                    add("src/main.rs".into(), kind);
                } else {
                    let flat = PathBuf::from(dir).join(format!("{target_name}.rs"));

                    if files.contains_key(doc.root.join(&flat).as_path()) {
                        add(flat, kind);
                    } else {
                        add(PathBuf::from(dir).join(target_name).join("main.rs"), kind);
                    }
                }
            }
        }

        let auto_key = match kind {
            TargetKind::Binary => "autobins",
            TargetKind::Example => "autoexamples",
            TargetKind::Test => "autotests",
            TargetKind::Bench => "autobenches",
            _ => unreachable!(),
        };

        if doc.value["package"].get(auto_key).and_then(Value::as_bool) == Some(false) {
            continue;
        }

        if kind == TargetKind::Binary && !explicit_names.contains(&name) {
            add("src/main.rs".into(), kind);
        }

        for path in files.keys() {
            let Ok(relative) = path.strip_prefix(doc.root.join(dir)) else {
                continue;
            };

            let parts: Vec<_> = relative.components().collect();
            let target_name =
                if parts.len() == 1 && relative.extension().is_some_and(|ext| ext == "rs") {
                    relative.file_stem().and_then(|v| v.to_str())
                } else if parts.len() == 2 && relative.file_name().is_some_and(|v| v == "main.rs") {
                    relative
                        .parent()
                        .and_then(Path::file_name)
                        .and_then(|v| v.to_str())
                } else {
                    None
                };

            if target_name.is_some_and(|name| !explicit_names.contains(&name)) {
                add(PathBuf::from(dir).join(relative), kind);
            }
        }
    }

    targets.sort_unstable_by_key(|target| target.root);
    targets
}
