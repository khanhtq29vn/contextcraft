//! R DESCRIPTION fields and named dependencies between indexed local packages.

use std::collections::BTreeMap;

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{PackageDependency, PackageResolution};

fn fields(source: &str) -> Option<BTreeMap<String, String>> {
    let mut fields = BTreeMap::<String, String>::new();
    let mut previous = None;
    for line in source.lines().filter(|line| !line.trim().is_empty()) {
        if line.starts_with(char::is_whitespace) {
            let value = fields.get_mut(previous.as_ref()?)?;
            value.push(' ');
            value.push_str(line.trim());
        } else {
            let (key, value) = line.split_once(':')?;
            if key.is_empty() || key.contains(char::is_whitespace) || fields.contains_key(key) {
                return None;
            }
            fields.insert(key.into(), value.trim().into());
            previous = Some(key.to_owned());
        }
    }
    Some(fields)
}

fn names(value: &str) -> impl Iterator<Item = &str> {
    value
        .split(',')
        .filter_map(|item| item.trim().split(['(', ' ', '\t']).next())
        .filter(|name| !name.is_empty() && *name != "R")
}

pub(super) fn attached_packages(source: &str) -> Vec<String> {
    fields(source)
        .and_then(|fields| fields.get("Depends").cloned())
        .map(|value| names(&value).map(str::to_owned).collect())
        .unwrap_or_default()
}

/// Reads DESCRIPTION names and links unambiguous declared local package dependencies.
///
/// # Errors
///
/// Returns an error for unreadable, invalid UTF-8, or malformed DESCRIPTION files.
/// Oversized files and dependencies outside the indexed repository are skipped.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let mut requirements = Vec::new();
    for (id, package) in index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("r"))
    {
        let Some(manifest) = package.manifests.first() else {
            continue;
        };
        let Some(source) = local::read(index, manifest, config)? else {
            continue;
        };
        let fields = fields(&source).ok_or_else(|| Error::Manifest {
            path: manifest.clone(),
            message: "invalid DESCRIPTION fields".into(),
        })?;
        let mut package = package.clone();
        package.name = fields.get("Package").cloned();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| {
                file.package_id == id
                    && file.language == Some("r")
                    && file.path.starts_with(package.root.join("R"))
            })
            .map(|(file, _)| file)
            .collect();
        let mut dependencies = Vec::new();
        for field in ["Depends", "Imports", "LinkingTo", "Suggests", "Enhances"] {
            if let Some(value) = fields.get(field) {
                dependencies.extend(names(value).map(str::to_owned));
            }
        }
        requirements.push((id, dependencies));
        resolution.packages.insert(id, package);
    }
    for (id, names) in requirements {
        for name in names {
            let candidates: Vec<_> = resolution
                .packages
                .iter()
                .filter(|(target, metadata)| *target != id && metadata.name.as_ref() == Some(&name))
                .map(|(target, _)| target)
                .collect();
            if let [target] = candidates.as_slice() {
                resolution.packages[id]
                    .dependencies
                    .push(PackageDependency {
                        alias: name,
                        package: *target,
                    });
            }
        }
    }
    Ok(resolution)
}
