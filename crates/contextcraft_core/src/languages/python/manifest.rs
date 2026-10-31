//! Discover local package metadata and workspace relationships.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::str::FromStr;

use globset::{GlobBuilder, GlobSetBuilder};
use la_arena::ArenaMap;
use pep508_rs::{PackageName, Requirement, VersionOrUrl};
use toml::Value;
use tree_sitter as ts;

use super::dependencies;
use crate::Config;
use crate::error::Error;
use crate::index::{Index, PackageId};
use crate::package::{
    Package, PackageDependency, PackageResolution, Workspace, local_path, read_toml, relative_path,
};

/// Source roots used to resolve modules owned by a Python package.
#[derive(Debug)]
pub struct PythonPackage {
    /// Configured or inferred import roots, in discovery order.
    pub roots: Vec<SourceRoot>,
}

/// Maps a repository directory to an importable module prefix.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceRoot {
    /// Source directory relative to the repository root.
    pub path: PathBuf,
    /// Module prefix mounted at this directory. Empty for an ordinary import root.
    pub prefix: Vec<String>,
}

pub(super) fn is_setup_script(index: &Index, path: &Path, config: &Config) -> Result<bool, Error> {
    let mut source = Vec::new();
    let limit = config.max_file_size_bytes.get();
    let path = index.root.join(path);
    fs::File::open(&path)
        .and_then(|file| {
            file.take((limit as u64).saturating_add(1))
                .read_to_end(&mut source)
        })
        .map_err(|source| Error::Io { path, source })?;

    if source.len() > limit {
        return Ok(false);
    }

    let mut parser = ts::Parser::new();
    parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
    let tree = parser.parse(&source, None).ok_or(Error::Parse)?;
    let mut cursor = tree.walk();
    let mut imports = Vec::new();
    let mut calls = HashSet::new();

    'walk: loop {
        let node = cursor.node();

        match node.kind() {
            "import_statement" | "import_from_statement" => {
                dependencies::extract(node, &source, &mut imports);
            }
            "call" => {
                if let Some(function) = node.child_by_field_name("function")
                    && matches!(function.kind(), "identifier" | "attribute")
                    && let Ok(name) = function.utf8_text(&source)
                {
                    calls.insert(
                        name.chars()
                            .filter(|character| !character.is_whitespace())
                            .collect::<String>(),
                    );
                }
            }
            _ => {}
        }

        if cursor.goto_first_child() {
            continue;
        }

        while !cursor.goto_next_sibling() {
            if !cursor.goto_parent() {
                break 'walk;
            }
        }
    }

    // A module named setup.py is only a project boundary when it calls a packaging API.
    let providers = ["setuptools", "distutils.core", "setuptools._distutils.core"];

    for import in imports {
        if import.level != 0 {
            continue;
        }

        let module = import.module.join(".");

        if !import.from && providers.contains(&module.as_str()) {
            let binding = import.alias.as_deref().unwrap_or(&module);

            if calls.contains(&format!("{binding}.setup")) {
                return Ok(true);
            }
        }

        for name in import.names {
            let path = name.path.join(".");
            let qualified = format!("{module}.{path}");
            let binding = name.alias.as_deref().unwrap_or(&path);
            let function = if qualified
                .strip_suffix(".setup")
                .is_some_and(|provider| providers.contains(&provider))
            {
                binding.to_owned()
            } else if providers.contains(&qualified.as_str()) {
                format!("{binding}.setup")
            } else {
                continue;
            };

            if calls.contains(&function) {
                return Ok(true);
            }
        }
    }

    Ok(false)
}

/// Discovers Python source roots, uv workspaces, and explicit local dependencies.
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
) -> Result<(PackageResolution, ArenaMap<PackageId, PythonPackage>), Error> {
    let mut documents = BTreeMap::new();
    let mut resolution = PackageResolution::default();

    for (id, package) in index.packages.iter() {
        if package.language != Some("python") {
            continue;
        }

        let Some(manifest) = package.manifests.iter().find(|path| {
            path.file_name()
                .is_some_and(|name| name == "pyproject.toml")
        }) else {
            continue;
        };

        let Some(value) = read_toml(index, manifest, config)? else {
            continue;
        };

        let mut package = package.clone();
        package.name = value
            .get("project")
            .and_then(|project| project.get("name"))
            .and_then(Value::as_str)
            .map(str::to_owned);

        resolution.packages.insert(id, package);
        documents.insert(id, value);
    }

    let (workspaces, owners) = discover_workspaces(index, &documents, &resolution.packages)?;
    resolution.workspaces = workspaces;

    link_dependencies(index, &documents, &owners, &mut resolution)?;

    let mut packages = ArenaMap::new();

    for (id, package) in index.packages.iter() {
        if package.language == Some("python")
            || package.language.is_none()
                && index
                    .files
                    .iter()
                    .any(|(_, file)| file.package_id == id && file.language == Some("python"))
        {
            packages.insert(
                id,
                PythonPackage {
                    roots: source_roots(index, id, documents.get(&id)),
                },
            );
        }
    }

    Ok((resolution, packages))
}

fn discover_workspaces(
    index: &Index,
    documents: &BTreeMap<PackageId, Value>,
    packages: &ArenaMap<PackageId, Package>,
) -> Result<(Vec<Workspace>, HashMap<PackageId, PackageId>), Error> {
    let mut workspaces = Vec::new();
    let mut owners = HashMap::new();

    for (&id, document) in documents {
        let Some(workspace) = document
            .get("tool")
            .and_then(|tool| tool.get("uv"))
            .and_then(|uv| uv.get("workspace"))
        else {
            continue;
        };

        let package = &index.packages[id];
        let manifest = package.root.join("pyproject.toml");
        let mut patterns = GlobSetBuilder::new();

        if let Some(members) = workspace.get("members") {
            let members = members.as_array().ok_or_else(|| Error::Manifest {
                path: manifest.clone(),
                message: "tool.uv.workspace.members must be an array of strings".into(),
            })?;

            for member in members {
                let pattern = member.as_str().ok_or_else(|| Error::Manifest {
                    path: manifest.clone(),
                    message: "tool.uv.workspace.members must be an array of strings".into(),
                })?;

                patterns.add(
                    GlobBuilder::new(pattern.trim_start_matches("./").trim_end_matches('/'))
                        .literal_separator(true)
                        .build()
                        .map_err(|error| Error::Manifest {
                            path: manifest.clone(),
                            message: error.to_string(),
                        })?,
                );
            }
        }

        let patterns = patterns.build().map_err(|error| Error::Manifest {
            path: manifest,
            message: error.to_string(),
        })?;
        let mut members = Vec::new();

        for &candidate in documents.keys() {
            if packages[candidate].name.is_none() {
                continue;
            }

            let member = &index.packages[candidate];
            let relative = relative_path(&package.root, &member.root);

            if candidate != id && !patterns.is_match(relative) {
                continue;
            }

            if owners
                .insert(candidate, id)
                .is_some_and(|owner| owner != id)
            {
                return Err(Error::Manifest {
                    path: member.root.join("pyproject.toml"),
                    message: "package belongs to multiple uv workspaces".into(),
                });
            }

            members.push(candidate);
        }

        workspaces.push(Workspace {
            root: package.root.clone(),
            language: "python",
            members,
        });
    }

    Ok((workspaces, owners))
}

fn link_dependencies(
    index: &Index,
    documents: &BTreeMap<PackageId, Value>,
    owners: &HashMap<PackageId, PackageId>,
    resolution: &mut PackageResolution,
) -> Result<(), Error> {
    let names: HashMap<_, _> = resolution
        .packages
        .iter()
        .filter_map(|(id, package)| {
            PackageName::from_str(package.name.as_deref()?)
                .ok()
                .map(|name| (id, name))
        })
        .collect();

    for (&id, document) in documents {
        let owner = owners.get(&id).copied().unwrap_or(id);

        let mut dependencies = Vec::new();

        for requirement in requirements(document) {
            let requirement: Requirement =
                requirement
                    .parse()
                    .map_err(|error: pep508_rs::Pep508Error| Error::Manifest {
                        path: index.packages[id].root.join("pyproject.toml"),
                        message: error.to_string(),
                    })?;
            let source = uv_source(document, &requirement.name)
                .map(|source| (source, id))
                .or_else(|| {
                    uv_source(documents.get(&owner)?, &requirement.name)
                        .map(|source| (source, owner))
                });

            let mut candidates = Vec::new();

            if let Some((source, origin)) = source {
                let sources = source
                    .as_array()
                    .map(Vec::as_slice)
                    .unwrap_or_else(|| std::slice::from_ref(source));

                for source in sources {
                    if source.get("workspace").and_then(Value::as_bool) == Some(true) {
                        candidates.extend(names.iter().filter_map(|(&target, name)| {
                            (name == &requirement.name
                                && owners.get(&target).copied() == Some(owner))
                            .then_some(target)
                        }));
                    } else if let Some(path) = source.get("path").and_then(Value::as_str)
                        && let Some(root) =
                            local_path(index, &index.packages[origin].root.join(path))
                    {
                        candidates.extend(names.iter().filter_map(|(&target, name)| {
                            (name == &requirement.name && index.packages[target].root == root)
                                .then_some(target)
                        }));
                    }
                }
            } else if let Some(VersionOrUrl::Url(url)) = &requirement.version_or_url
                && let Ok(path) = url.raw().to_file_path()
                && let Some(root) = local_path(index, &path)
            {
                candidates.extend(names.iter().filter_map(|(&target, name)| {
                    (name == &requirement.name && index.packages[target].root == root)
                        .then_some(target)
                }));
            }

            candidates.sort_unstable();
            candidates.dedup();

            for target in candidates {
                let dependency = PackageDependency {
                    alias: requirement.name.to_string(),
                    package: target,
                };

                if target != id && !dependencies.contains(&dependency) {
                    dependencies.push(dependency);
                }
            }
        }

        resolution.packages[id].dependencies = dependencies;
    }

    Ok(())
}

fn requirements(document: &Value) -> Vec<&str> {
    // Keep all extras, groups, and marker environments as possible local dependencies.
    let mut dependency_lists = Vec::new();

    if let Some(project) = document.get("project") {
        dependency_lists.extend(project.get("dependencies"));

        if let Some(optional) = project
            .get("optional-dependencies")
            .and_then(Value::as_table)
        {
            dependency_lists.extend(optional.values());
        }
    }

    if let Some(groups) = document.get("dependency-groups").and_then(Value::as_table) {
        dependency_lists.extend(groups.values());
    }

    dependency_lists.extend(
        document
            .get("tool")
            .and_then(|tool| tool.get("uv"))
            .and_then(|uv| uv.get("dev-dependencies")),
    );

    dependency_lists
        .into_iter()
        .filter_map(Value::as_array)
        .flatten()
        .filter_map(Value::as_str)
        .collect()
}

fn uv_source<'a>(document: &'a Value, name: &PackageName) -> Option<&'a Value> {
    let sources = document
        .get("tool")?
        .get("uv")?
        .get("sources")?
        .as_table()?;

    sources.iter().find_map(|(candidate, source)| {
        (PackageName::from_str(candidate).ok().as_ref() == Some(name)).then_some(source)
    })
}

fn source_roots(index: &Index, id: PackageId, document: Option<&Value>) -> Vec<SourceRoot> {
    let package = &index.packages[id];
    let mut roots = Vec::new();
    let mut configured = false;
    let mut add = |path: &str, prefix: Vec<String>| {
        configured = true;

        if let Some(path) = local_path(index, &package.root.join(path)) {
            let root = SourceRoot { path, prefix };

            if !roots.contains(&root) {
                roots.push(root);
            }
        }
    };

    if let Some(tool) = document.and_then(|document| document.get("tool")) {
        if let Some(setuptools) = tool.get("setuptools") {
            if let Some(directories) = setuptools.get("package-dir").and_then(Value::as_table) {
                for (name, path) in directories {
                    if let Some(path) = path.as_str() {
                        let prefix = if name.is_empty() {
                            Vec::new()
                        } else {
                            name.split('.').map(str::to_owned).collect()
                        };

                        add(path, prefix);
                    }
                }
            }

            if let Some(directories) = setuptools
                .get("packages")
                .and_then(|packages| packages.get("find"))
                .and_then(|find| find.get("where"))
                .and_then(Value::as_array)
            {
                for directory in directories.iter().filter_map(Value::as_str) {
                    add(directory, Vec::new());
                }
            }
        }

        if let Some(path) = tool
            .get("maturin")
            .and_then(|maturin| maturin.get("python-source"))
            .and_then(Value::as_str)
        {
            add(path, Vec::new());
        }

        if let Some(packages) = tool
            .get("hatch")
            .and_then(|hatch| hatch.get("build"))
            .and_then(|build| build.get("targets"))
            .and_then(|targets| targets.get("wheel"))
            .and_then(|wheel| wheel.get("packages"))
            .and_then(Value::as_array)
        {
            for path in packages.iter().filter_map(Value::as_str) {
                if let Some(parent) = Path::new(path).parent() {
                    add(parent.to_str().unwrap_or(""), Vec::new());
                }
            }
        }
    }

    if !configured {
        let src = package.root.join("src");

        if index.files.iter().any(|(_, file)| {
            file.package_id == id && file.language == Some("python") && file.path.starts_with(&src)
        }) {
            roots.push(SourceRoot {
                path: src,
                prefix: Vec::new(),
            });
        }

        let initializer = index.files.iter().any(|(_, file)| {
            file.package_id == id
                && file.path.parent() == Some(package.root.as_path())
                && matches!(
                    file.path.file_name().and_then(|name| name.to_str()),
                    Some("__init__.py" | "__init__.pyi" | "__init__.pyw")
                )
        });

        if initializer
            && let Some(name) = index
                .root
                .join(&package.root)
                .file_name()
                .and_then(|name| name.to_str())
        {
            roots.push(SourceRoot {
                path: package.root.clone(),
                prefix: vec![name.to_owned()],
            });
        }

        roots.push(SourceRoot {
            path: package.root.clone(),
            prefix: Vec::new(),
        });
    }

    roots
}
