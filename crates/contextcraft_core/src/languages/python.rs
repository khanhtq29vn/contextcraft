//! Python parsing, package discovery, and local import resolution.

use std::path::Path;
use std::sync::{Arc, Mutex};

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::{Language, LanguageAnalysis};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index, PackageId};
use crate::package::PackageResolution;
use crate::repo::Repository;

pub mod dependencies;
pub mod manifest;
pub mod resolve;

/// Python grammar with repository-local source roots and package visibility.
#[derive(Debug, Default)]
pub struct Python {
    packages: Arc<ArenaMap<PackageId, manifest::PythonPackage>>,
}

impl Language for Python {
    fn id(&self) -> &'static str {
        "python"
    }

    fn grammar(&self) -> ts::Language {
        tree_sitter_python::LANGUAGE.into()
    }

    fn source_query(&self) -> &'static str {
        include_str!("../../queries/python.scm")
    }

    fn is_package_manifest(
        &self,
        index: &Index,
        path: &Path,
        config: &Config,
    ) -> Result<bool, Error> {
        if path.file_name().is_some_and(|name| name == "setup.py") {
            return manifest::is_setup_script(index, path, config);
        }

        Ok(true)
    }

    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error> {
        let (resolution, packages) = manifest::discover(index, config)?;
        self.packages = Arc::new(packages);

        Ok(resolution)
    }

    fn create_analysis(&self) -> Box<dyn LanguageAnalysis> {
        Box::new(PythonAnalysis {
            packages: Arc::clone(&self.packages),
            imports: Mutex::new(ArenaMap::new()),
        })
    }

    fn ignore_patterns(&self) -> &'static [&'static str] {
        &[
            "!**/uv.lock",
            "!**/poetry.lock",
            "!**/pdm.lock",
            "!**/Pipfile.lock",
            "!**/pixi.lock",
            "!**/conda-lock.yml",
            "!**/conda-lock.yaml",
            "!**/__pycache__/**",
            "!**/*.pyc",
            "!**/*.pyo",
            "!**/.pytest_cache/**",
            "!**/.mypy_cache/**",
            "!**/.pytype/**",
            "!**/.pyre/**",
            "!**/.ruff_cache/**",
            "!**/.tox/**",
            "!**/.nox/**",
            "!**/*.egg-info/**",
            "!**/*.egg",
            "!**/*.whl",
            "!**/.coverage",
            "!**/.coverage.*",
            "!**/htmlcov/**",
        ]
    }

    fn package_markers(&self) -> &'static [&'static str] {
        &["pyproject.toml", "setup.py", "setup.cfg"]
    }

    fn package_metadata_files(&self) -> &'static [&'static str] {
        &[
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "MANIFEST.in",
            "uv.toml",
            "uv.lock",
            "poetry.toml",
            "poetry.lock",
            "pdm.toml",
            "pdm.lock",
            "Pipfile",
            "Pipfile.lock",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements.in",
            "requirements-dev.in",
            "constraints.txt",
            "hatch.toml",
            "pixi.toml",
            "pixi.lock",
            "environment.yml",
            "environment.yaml",
            "conda-lock.yml",
            ".python-version",
            ".python-versions",
        ]
    }

    fn file_extensions(&self) -> &'static [&'static str] {
        &[".py", ".pyi", ".pyw"]
    }
}

#[derive(Debug)]
struct PythonAnalysis {
    packages: Arc<ArenaMap<PackageId, manifest::PythonPackage>>,
    imports: Mutex<ArenaMap<FileId, Vec<dependencies::Import>>>,
}

impl LanguageAnalysis for PythonAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut imports = Vec::new();

        for &node in nodes {
            dependencies::extract(node, source, &mut imports);
        }

        self.imports.lock().unwrap().insert(file, imports);
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        _repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let imports = self.imports.lock().unwrap();

        resolve::resolve(index, &self.packages, &imports)
    }
}
