//! Shared local package, dependency, and workspace metadata.

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use la_arena::ArenaMap;

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};

/// Local package metadata shared by language implementations.
#[derive(Debug, Clone)]
pub struct Package {
    /// Package directory relative to the repository root.
    pub root: PathBuf,
    /// Declared package name, if available from its manifests.
    pub name: Option<String>,
    /// Package language ID, or `None` for the fallback package.
    pub language: Option<&'static str>,
    /// Package manifest paths relative to the repository root.
    pub manifests: Vec<PathBuf>,
    /// Known target entry files, such as library and executable roots.
    pub targets: Vec<FileId>,
    /// Dependency scopes and other resolution rules remain with the language.
    pub dependencies: Vec<PackageDependency>,
}

/// Named dependency on another indexed local package.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackageDependency {
    /// Name used to refer to the dependency in this language.
    pub alias: String,
    /// Dependency package ID in the associated index.
    pub package: PackageId,
}

/// Local package membership declared by a language-specific workspace.
#[derive(Debug)]
pub struct Workspace {
    /// Workspace directory relative to the repository root.
    pub root: PathBuf,
    /// Language whose manifest defines this workspace.
    pub language: &'static str,
    /// Workspace member IDs in the associated index.
    pub members: Vec<PackageId>,
}

/// Package updates and workspaces produced by language-specific resolution.
#[derive(Debug, Default)]
pub struct PackageResolution {
    /// Resolved metadata replacing the corresponding indexed packages.
    pub packages: ArenaMap<PackageId, Package>,
    /// Discovered workspace definitions.
    pub workspaces: Vec<Workspace>,
}

pub(crate) fn read_toml(
    index: &Index,
    manifest: &Path,
    config: &Config,
) -> Result<Option<toml::Value>, Error> {
    let path = index.root.join(manifest);
    let limit = config.max_file_size_bytes.get();
    let mut bytes = Vec::new();

    fs::File::open(&path)
        .and_then(|file| {
            file.take((limit as u64).saturating_add(1))
                .read_to_end(&mut bytes)
        })
        .map_err(|source| Error::Io { path, source })?;

    if bytes.len() > limit {
        return Ok(None);
    }

    let text = std::str::from_utf8(&bytes).map_err(|error| Error::Manifest {
        path: manifest.to_path_buf(),
        message: error.to_string(),
    })?;
    let value = toml::from_str(text).map_err(|error: toml::de::Error| Error::Manifest {
        path: manifest.to_path_buf(),
        message: error.to_string(),
    })?;

    Ok(Some(value))
}

pub(crate) fn local_path(index: &Index, path: &Path) -> Option<PathBuf> {
    index
        .root
        .join(path)
        .canonicalize()
        .ok()?
        .strip_prefix(&index.root)
        .ok()
        .map(Path::to_path_buf)
}

pub(crate) fn relative_path(base: &Path, path: &Path) -> PathBuf {
    let shared = base
        .components()
        .zip(path.components())
        .take_while(|(a, b)| a == b)
        .count();
    let mut relative = PathBuf::new();

    for _ in base.components().skip(shared) {
        relative.push("..");
    }

    for component in path.components().skip(shared) {
        relative.push(component.as_os_str());
    }

    relative
}
