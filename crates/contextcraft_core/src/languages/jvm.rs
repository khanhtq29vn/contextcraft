//! Shared Java/Kotlin project ownership and cross-language symbol resolution.

use std::collections::BTreeMap;

use la_arena::ArenaMap;

use super::local::{self, References};
use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::{Package, PackageResolution};
use crate::repo::Repository;

pub(super) fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages: BTreeMap<_, _> = super::gradle::packages(index, config)?
        .into_iter()
        .map(|package| (package.root.clone(), package))
        .collect();
    for package in local::discover(index, "jvm", &[], &["pom.xml"]) {
        packages
            .entry(package.root.clone())
            .and_modify(|existing| existing.manifests.extend(package.manifests.clone()))
            .or_insert(package);
    }
    Ok(packages.into_values().collect())
}

pub(super) fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = super::gradle::discover(index, config)?;
    let maven = super::java::manifest::discover(index, config)?;
    for (id, package) in maven.packages {
        let existing = resolution
            .packages
            .entry(id)
            .or_insert_with(|| package.clone());
        existing.name = package.name.or_else(|| existing.name.clone());
        existing.dependencies.extend(package.dependencies);
        existing.targets.extend(package.targets);
        existing.targets.sort_unstable();
        existing.targets.dedup();
    }
    resolution.workspaces.extend(maven.workspaces);
    Ok(resolution)
}

pub(super) fn resolve(
    index: &Index,
    repository: &Repository,
    references: &ArenaMap<FileId, References>,
    language: &str,
) -> Vec<(FileId, FileId)> {
    let mut combined = references.clone();
    for other in ["java", "kotlin"] {
        if other != language
            && let Some(analysis) = repository.analyses.get(other)
        {
            combined.extend(analysis.symbol_references());
        }
    }
    local::resolve_symbols(index, repository, &combined)
}
