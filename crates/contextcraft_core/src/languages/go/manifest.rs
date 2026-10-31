//! Discover local package metadata and workspace relationships.

use std::collections::BTreeMap;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use la_arena::ArenaMap;

use super::dependencies::unquote;
use crate::Config;
use crate::error::Error;
use crate::index::{Index, PackageId};
use crate::package::{PackageDependency, PackageResolution, Workspace, local_path};

/// Local module build contexts visible to one Go package.
#[derive(Debug, Default)]
pub struct GoPackage {
    /// Visible module paths paired with their indexed local package IDs.
    pub modules: Vec<(String, PackageId)>,
}

#[derive(Default)]
struct Document {
    module: Option<String>,
    requires: Vec<(String, String)>,
    replacements: Vec<Replacement>,
    uses: Vec<PathBuf>,
}

struct Replacement {
    module: String,
    version: Option<String>,
    directory: Option<PathBuf>,
}

/// Discovers Go modules, workspaces, and local replacement dependencies.
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
) -> Result<(PackageResolution, ArenaMap<PackageId, GoPackage>), Error> {
    let mut documents = BTreeMap::new();
    let mut resolution = PackageResolution::default();

    for (id, package) in index.packages.iter() {
        if package.language != Some("go") {
            continue;
        }

        let manifest = package.root.join("go.mod");
        let Some(document) = read(index, &manifest, config)? else {
            continue;
        };
        let Some(name) = &document.module else {
            return Err(Error::Manifest {
                path: manifest,
                message: "missing module directive".into(),
            });
        };
        let mut package = package.clone();
        package.name = Some(name.clone());
        resolution.packages.insert(id, package);
        documents.insert(id, document);
    }

    let roots: BTreeMap<_, _> = documents
        .keys()
        .map(|&id| (index.packages[id].root.as_path(), id))
        .collect();
    let mut workspaces = Vec::new();

    for (_, file) in index.files.iter() {
        if file.path.file_name().is_none_or(|name| name != "go.work") {
            continue;
        }

        let Some(document) = read(index, &file.path, config)? else {
            continue;
        };
        let root = file.path.parent().unwrap();
        let mut members: Vec<_> = document
            .uses
            .iter()
            .filter_map(|path| local_path(index, &root.join(path)))
            .filter_map(|path| roots.get(path.as_path()).copied())
            .collect();
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: root.to_path_buf(),
            language: "go",
            members,
        });
        workspaces.push(document);
    }

    let mut packages = ArenaMap::new();

    for &id in documents.keys() {
        let workspace = resolution
            .workspaces
            .iter()
            .enumerate()
            .filter(|(_, workspace)| workspace.members.contains(&id))
            .max_by_key(|(_, workspace)| workspace.root.components().count());
        let members = workspace
            .map(|(_, workspace)| workspace.members.as_slice())
            .unwrap_or(std::slice::from_ref(&id));
        let mut modules = Vec::new();

        for &member in members {
            modules.push((documents[&member].module.clone().unwrap(), member));
        }

        // Only main modules supply replacements, including for transitive requirements.
        let mut cursor = 0;

        while cursor < modules.len() {
            let document = &documents[&modules[cursor].1];

            for (name, version) in &document.requires {
                if modules.iter().any(|(module, _)| module == name) {
                    continue;
                }

                let workspace_replacement = workspace.and_then(|(position, workspace)| {
                    replacement(&workspaces[position], name, version)
                        .map(|replacement| (replacement, workspace.root.as_path()))
                });
                let candidates: Vec<_> = if let Some(replacement) = workspace_replacement {
                    vec![replacement]
                } else {
                    members
                        .iter()
                        .filter_map(|member| {
                            replacement(&documents[member], name, version).map(|replacement| {
                                (replacement, index.packages[*member].root.as_path())
                            })
                        })
                        .collect()
                };
                let mut targets = Vec::new();

                for (replacement, base) in candidates {
                    let target = replacement
                        .directory
                        .as_ref()
                        .and_then(|path| local_path(index, &base.join(path)))
                        .and_then(|path| roots.get(path.as_path()).copied());
                    targets.push(target);
                }

                targets.sort_unstable();
                targets.dedup();

                // Conflicting replacements must not pick an arbitrary local module.
                if let [Some(target)] = targets.as_slice() {
                    modules.push((name.clone(), *target));
                }
            }

            cursor += 1;
        }

        resolution.packages[id].dependencies = modules
            .iter()
            .filter(|(_, target)| *target != id)
            .map(|(alias, target)| PackageDependency {
                alias: alias.clone(),
                package: *target,
            })
            .collect();
        packages.insert(id, GoPackage { modules });
    }

    Ok((resolution, packages))
}

fn replacement<'a>(document: &'a Document, name: &str, version: &str) -> Option<&'a Replacement> {
    document
        .replacements
        .iter()
        .find(|replacement| {
            replacement.module == name && replacement.version.as_deref() == Some(version)
        })
        .or_else(|| {
            document
                .replacements
                .iter()
                .find(|replacement| replacement.module == name && replacement.version.is_none())
        })
}

fn read(index: &Index, path: &Path, config: &Config) -> Result<Option<Document>, Error> {
    let mut bytes = Vec::new();
    fs::File::open(index.root.join(path))
        .and_then(|file| {
            file.take((config.max_file_size_bytes.get() as u64).saturating_add(1))
                .read_to_end(&mut bytes)
        })
        .map_err(|source| Error::Io {
            path: index.root.join(path),
            source,
        })?;

    if bytes.len() > config.max_file_size_bytes.get() {
        return Ok(None);
    }

    let invalid = || Error::Manifest {
        path: path.to_path_buf(),
        message: "invalid Go module or workspace directive".into(),
    };
    let text = std::str::from_utf8(&bytes).map_err(|_| invalid())?;
    let tokens = tokenize(text).ok_or_else(invalid)?;
    let mut document = Document::default();
    let mut block = None;

    for line in tokens
        .split(|token| token == "\n")
        .filter(|line| !line.is_empty())
    {
        if line == [")"] {
            if block.take().is_none() {
                return Err(invalid());
            }
            continue;
        }

        let (directive, arguments) = if let Some(directive) = block {
            (directive, line)
        } else {
            (line[0].as_str(), &line[1..])
        };

        if arguments == ["("] {
            if block.is_some() {
                return Err(invalid());
            }
            block = Some(directive);
            continue;
        }

        match (directive, arguments) {
            ("module", [name]) => document.module = Some(name.clone()),
            ("require", [name, version]) => document.requires.push((name.clone(), version.clone())),
            ("use", [directory]) => document.uses.push(directory.into()),
            ("replace", arguments) => {
                let arrow = arguments
                    .iter()
                    .position(|token| token == "=>")
                    .ok_or_else(invalid)?;
                let (module, version) = match &arguments[..arrow] {
                    [module] => (module.clone(), None),
                    [module, version] => (module.clone(), Some(version.clone())),
                    _ => return Err(invalid()),
                };
                let directory = match &arguments[arrow + 1..] {
                    [directory]
                        if Path::new(directory).is_absolute()
                            || directory == "."
                            || directory == ".."
                            || directory.starts_with("./")
                            || directory.starts_with("../") =>
                    {
                        Some(directory.into())
                    }
                    [_, _] => None,
                    _ => return Err(invalid()),
                };
                document.replacements.push(Replacement {
                    module,
                    version,
                    directory,
                });
            }
            ("module" | "require" | "use", _) => return Err(invalid()),
            _ => {}
        }
    }

    if block.is_some() {
        return Err(invalid());
    }

    Ok(Some(document))
}

fn tokenize(text: &str) -> Option<Vec<String>> {
    let mut tokens = Vec::new();
    let mut chars = text.char_indices().peekable();

    while let Some((start, character)) = chars.next() {
        match character {
            '\n' => tokens.push("\n".into()),
            character if character.is_whitespace() => {}
            '/' if chars.peek().is_some_and(|(_, next)| *next == '/') => {
                for (_, character) in chars.by_ref() {
                    if character == '\n' {
                        tokens.push("\n".into());
                        break;
                    }
                }
            }
            '"' | '`' => {
                let mut end = None;

                while let Some((position, next)) = chars.next() {
                    if next == character {
                        end = Some(position + 1);
                        break;
                    }
                    if character == '"' && next == '\\' {
                        chars.next()?;
                    } else if character == '"' && next == '\n' {
                        return None;
                    }
                }

                tokens.push(unquote(&text[start..end?])?);
            }
            '(' | ')' => tokens.push(character.to_string()),
            _ => {
                let mut end = start + character.len_utf8();

                while let Some(&(position, next)) = chars.peek() {
                    if next.is_whitespace()
                        || matches!(next, '(' | ')')
                        || text[position..].starts_with("//")
                    {
                        break;
                    }
                    chars.next();
                    end = position + next.len_utf8();
                }

                tokens.push(text[start..end].to_owned());
            }
        }
    }

    Some(tokens)
}
