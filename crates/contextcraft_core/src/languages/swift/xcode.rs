//! Static Xcode source membership, target dependencies, and workspace references.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use apple_plist::Value;
use la_arena::ArenaMap;

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::languages::local::{self, References};
use crate::package::{Package, PackageDependency, PackageResolution, Workspace, local_path};
use crate::repo::Repository;

type Objects = apple_plist::Dictionary;

struct Target {
    id: String,
    name: String,
    files: Vec<FileId>,
    dependencies: Vec<(PathBuf, String)>,
}

struct Project {
    manifest: PathBuf,
    targets: Vec<Target>,
}

fn string<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value.as_dictionary()?.get(key)?.as_str()
}

fn array<'a>(value: &'a Value, key: &str) -> &'a [Value] {
    value
        .as_dictionary()
        .and_then(|dict| dict.get(key))
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or(&[])
}

fn group_paths(
    index: &Index,
    objects: &Objects,
    id: &str,
    base: &Path,
    root: &Path,
    seen: &mut HashSet<String>,
    paths: &mut HashMap<String, PathBuf>,
) {
    let mut pending = vec![(id.to_owned(), base.to_path_buf())];
    while let Some((id, parent)) = pending.pop() {
        if !seen.insert(id.clone()) {
            continue;
        }
        let Some(object) = objects.get(&id) else {
            continue;
        };
        let path = string(object, "path").unwrap_or("");
        if path.contains('$') {
            continue;
        }
        let base = match string(object, "sourceTree").unwrap_or("<group>") {
            "<group>" => parent.as_path(),
            "SOURCE_ROOT" => root,
            "<absolute>" => Path::new("/"),
            _ => continue,
        };
        let path = base.join(path);
        if let Some(path) = local_path(index, &path) {
            paths.insert(id, path);
        }
        for child in array(object, "children").iter().filter_map(Value::as_str) {
            pending.push((child.to_owned(), path.clone()));
        }
    }
}

fn parse(index: &Index, manifest: &Path, source: &str) -> Result<Project, Error> {
    let value = apple_plist::Decoder::new(source.as_bytes())
        .decode_value()
        .map_err(|error| Error::Manifest {
            path: manifest.to_path_buf(),
            message: error.to_string(),
        })?;
    let objects = value
        .as_dictionary()
        .and_then(|dict| dict.get("objects"))
        .and_then(Value::as_dictionary)
        .ok_or_else(|| Error::Manifest {
            path: manifest.to_path_buf(),
            message: "missing Xcode objects dictionary".into(),
        })?;
    let root = manifest.parent().unwrap().parent().unwrap();
    let mut paths = HashMap::new();
    for object in objects
        .values()
        .filter(|object| string(object, "isa") == Some("PBXProject"))
    {
        if let Some(group) = string(object, "mainGroup") {
            group_paths(
                index,
                objects,
                group,
                root,
                root,
                &mut HashSet::new(),
                &mut paths,
            );
        }
    }
    let files: HashMap<_, _> = index
        .files
        .iter()
        .filter(|(_, file)| file.language == Some("swift"))
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    let mut targets = Vec::new();

    for (id, object) in objects
        .iter()
        .filter(|(_, object)| string(object, "isa") == Some("PBXNativeTarget"))
    {
        let mut names = Vec::new();
        if let Some(configurations) =
            string(object, "buildConfigurationList").and_then(|id| objects.get(id))
        {
            for configuration in array(configurations, "buildConfigurations")
                .iter()
                .filter_map(Value::as_str)
                .filter_map(|id| objects.get(id))
            {
                if let Some(settings) = configuration
                    .as_dictionary()
                    .and_then(|dict| dict.get("buildSettings"))
                    && let Some(name) = string(settings, "PRODUCT_MODULE_NAME")
                    && !name.contains('$')
                {
                    names.push(name.to_owned());
                }
            }
        }
        names.sort();
        names.dedup();
        let name = match names.as_slice() {
            [name] => name.clone(),
            [] => string(object, "productName")
                .or_else(|| string(object, "name"))
                .unwrap_or("")
                .replace('-', "_"),
            _ => continue,
        };
        let mut source_files = Vec::new();
        for phase in array(object, "buildPhases")
            .iter()
            .filter_map(Value::as_str)
            .filter_map(|id| objects.get(id))
            .filter(|phase| string(phase, "isa") == Some("PBXSourcesBuildPhase"))
        {
            for file in array(phase, "files")
                .iter()
                .filter_map(Value::as_str)
                .filter_map(|id| objects.get(id))
            {
                if let Some(path) = string(file, "fileRef").and_then(|id| paths.get(id))
                    && let Some(&file) = files.get(path.as_path())
                {
                    source_files.push(file);
                }
            }
        }
        for group in array(object, "fileSystemSynchronizedGroups")
            .iter()
            .filter_map(Value::as_str)
        {
            let Some(path) = paths.get(group).cloned().or_else(|| {
                objects
                    .get(group)
                    .and_then(|object| string(object, "path"))
                    .and_then(|path| local_path(index, &root.join(path)))
            }) else {
                continue;
            };
            let mut excluded = Vec::new();
            if let Some(group) = objects.get(group) {
                for exception in array(group, "exceptions")
                    .iter()
                    .filter_map(Value::as_str)
                    .filter_map(|id| objects.get(id))
                    .filter(|exception| string(exception, "target") == Some(id))
                {
                    excluded.extend(
                        array(exception, "membershipExceptions")
                            .iter()
                            .filter_map(Value::as_str)
                            .map(|name| path.join(name)),
                    );
                }
            }
            source_files.extend(
                files
                    .iter()
                    .filter(|(file, _)| {
                        file.starts_with(&path)
                            && !excluded.iter().any(|excluded| file.starts_with(excluded))
                    })
                    .map(|(_, &id)| id),
            );
        }
        source_files.sort_unstable();
        source_files.dedup();
        let mut dependencies = Vec::new();
        for dependency in array(object, "dependencies")
            .iter()
            .filter_map(Value::as_str)
            .filter_map(|id| objects.get(id))
        {
            if let Some(target) = string(dependency, "target") {
                dependencies.push((manifest.to_path_buf(), target.into()));
            } else if let Some(proxy) =
                string(dependency, "targetProxy").and_then(|id| objects.get(id))
                && let Some(portal) = string(proxy, "containerPortal").and_then(|id| paths.get(id))
                && let Some(target) = string(proxy, "remoteGlobalIDString")
            {
                dependencies.push((portal.join("project.pbxproj"), target.into()));
            }
        }
        targets.push(Target {
            id: id.clone(),
            name,
            files: source_files,
            dependencies,
        });
    }
    Ok(Project {
        manifest: manifest.to_path_buf(),
        targets,
    })
}

pub(super) fn packages(index: &Index) -> Vec<Package> {
    index
        .files
        .iter()
        .filter(|(_, file)| {
            file.path
                .file_name()
                .is_some_and(|name| name == "project.pbxproj")
                && file.path.parent().is_some_and(|parent| {
                    parent
                        .extension()
                        .is_some_and(|extension| extension == "xcodeproj")
                })
        })
        .map(|(_, file)| {
            let mut package = local::package(
                file.path.parent().unwrap().parent().unwrap().to_path_buf(),
                "swift",
                file.path.clone(),
            );
            package.name = file
                .path
                .parent()
                .unwrap()
                .file_stem()
                .map(|name| name.to_string_lossy().into_owned());
            package
        })
        .collect()
}

pub(super) fn discover(
    index: &Index,
    config: &Config,
    resolution: &mut PackageResolution,
) -> Result<(), Error> {
    let mut projects = Vec::new();
    let mut owners = HashMap::new();
    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("swift"))
    {
        for manifest in package.manifests.iter().filter(|path| {
            path.file_name()
                .is_some_and(|name| name == "project.pbxproj")
        }) {
            let Some(source) = local::read(index, manifest, config)? else {
                continue;
            };
            let project = parse(index, manifest, &source)?;
            resolution.packages[id].targets.extend(
                project
                    .targets
                    .iter()
                    .flat_map(|target| target.files.iter().copied()),
            );
            owners.insert(manifest.clone(), id);
            projects.push(project);
        }
    }
    for project in &projects {
        let id = owners[&project.manifest];
        for target in &project.targets {
            for (manifest, target_id) in &target.dependencies {
                if let Some(&dependency) = owners.get(manifest)
                    && dependency != id
                {
                    resolution.packages[id]
                        .dependencies
                        .push(PackageDependency {
                            alias: target_id.clone(),
                            package: dependency,
                        });
                }
            }
        }
    }
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "contents.xcworkspacedata")
    }) {
        let Some(source) = local::read(index, &file.path, config)? else {
            continue;
        };
        let document = roxmltree::Document::parse(&source).map_err(|error| Error::Manifest {
            path: file.path.clone(),
            message: error.to_string(),
        })?;
        let root = file.path.parent().unwrap().parent().unwrap();
        let mut members = Vec::new();
        for node in document
            .descendants()
            .filter(|node| node.has_tag_name("FileRef"))
        {
            let mut locations = Vec::new();
            for ancestor in node.ancestors().filter(|node| node.is_element()) {
                if let Some(location) = ancestor.attribute("location") {
                    locations.push(location);
                }
            }
            let mut path = root.to_path_buf();
            for location in locations.into_iter().rev() {
                if let Some(value) = location.strip_prefix("group:") {
                    path.push(value);
                } else if let Some(value) = location.strip_prefix("container:") {
                    path = root.join(value);
                } else if let Some(value) = location.strip_prefix("absolute:") {
                    path = value.into();
                }
            }
            if let Some(path) = local_path(index, &path)
                && let Some(&member) = owners.get(&path.join("project.pbxproj"))
            {
                members.push(member);
            }
        }
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.to_path_buf(),
            language: "swift",
            members,
        });
    }
    Ok(())
}

pub(super) fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
) -> Vec<(FileId, FileId)> {
    let mut projects = Vec::new();
    for (file, source) in repository.sources.iter() {
        let path = &index.files[file].path;
        if path
            .file_name()
            .is_none_or(|name| name != "project.pbxproj")
        {
            continue;
        }
        if let Ok(source) = std::str::from_utf8(&source.bytes)
            && let Ok(project) = parse(index, path, source)
        {
            projects.push(project);
        }
    }
    let targets: HashMap<_, _> = projects
        .iter()
        .flat_map(|project| {
            project
                .targets
                .iter()
                .map(|target| ((project.manifest.as_path(), target.id.as_str()), target))
        })
        .collect();
    let mut edges = Vec::new();
    for project in &projects {
        for target in &project.targets {
            for &file in &target.files {
                let Some(references) = references.get(file) else {
                    continue;
                };
                for (manifest, id) in &target.dependencies {
                    if let Some(dependency) = targets.get(&(manifest.as_path(), id.as_str()))
                        && references
                            .imports
                            .iter()
                            .any(|(_, name)| name == &dependency.name)
                    {
                        edges.extend(
                            dependency
                                .files
                                .iter()
                                .filter(|&&file| repository.sources.get(file).is_some())
                                .map(|&dependency| (file, dependency)),
                        );
                    }
                }
            }
        }
    }
    local::finish(edges)
}
