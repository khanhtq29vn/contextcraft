//! Resolve captured references to indexed local files.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use la_arena::ArenaMap;

use crate::index::{FileId, Index};
use crate::package::local_path;
use crate::repo::Repository;

/// Resolves local includes using caller directories and literal compilation-database arguments.
///
/// Only readable indexed files are targets. Returns sorted, deduplicated edges.
pub fn resolve(
    index: &Index,
    repository: &Repository,
    includes: &ArenaMap<FileId, Vec<String>>,
) -> Vec<(FileId, FileId)> {
    // Includes can target textual .inc files or extensionless headers as well.
    let files: HashMap<_, _> = index
        .files
        .iter()
        .filter(|(id, _)| repository.sources.get(*id).is_some())
        .map(|(id, file)| (file.path.as_path(), id))
        .collect();
    let mut contexts = Vec::new();
    for (id, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "compile_commands.json")
    }) {
        let Some(source) = repository.sources.get(id) else {
            continue;
        };
        let Ok(commands) = serde_json::from_slice::<serde_json::Value>(&source.bytes) else {
            continue;
        };
        for command in commands.as_array().into_iter().flatten() {
            let Some(directory) = command.get("directory").and_then(serde_json::Value::as_str)
            else {
                continue;
            };
            let directory = if Path::new(directory).is_absolute() {
                PathBuf::from(directory)
            } else {
                index.root.join(file.path.parent().unwrap()).join(directory)
            };
            let Some(source) = command
                .get("file")
                .and_then(serde_json::Value::as_str)
                .and_then(|path| local_path(index, &directory.join(path)))
            else {
                continue;
            };
            let Some(arguments) = arguments(command) else {
                continue;
            };
            let mut paths = Vec::new();
            let mut i = 0;
            while i < arguments.len() {
                let argument = arguments[i].as_str();
                for flag in ["-iquote", "-isystem", "-idirafter", "-I", "/I"] {
                    if let Some(value) = argument.strip_prefix(flag) {
                        let value = if value.is_empty() {
                            i += 1;
                            arguments.get(i).map(String::as_str)
                        } else {
                            Some(value)
                        };
                        if let Some(value) = value {
                            let rank = match flag {
                                "-iquote" => 0,
                                "-I" | "/I" => 1,
                                "-isystem" => 2,
                                _ => 3,
                            };
                            paths.push((rank, directory.join(value)));
                        }
                        break;
                    }
                }
                i += 1;
            }
            paths.sort_by_key(|(rank, _)| *rank);
            contexts.push((source, paths));
        }
    }
    let mut edges = Vec::new();

    for (file, includes) in includes.iter() {
        let directory = index.files[file].path.parent().unwrap();

        for include in includes {
            let system = include.starts_with('<');
            let include = if system {
                include
                    .strip_prefix('<')
                    .and_then(|path| path.strip_suffix('>'))
                    .unwrap_or("")
            } else {
                include.as_str()
            };
            if include.is_empty() || Path::new(include).is_absolute() || include.contains('\0') {
                continue;
            }
            if !system
                && let Some(path) = local_path(index, &directory.join(include))
                && let Some(&target) = files.get(path.as_path())
            {
                if target != file {
                    edges.push((file, target));
                }
                continue;
            }
            let exact = contexts
                .iter()
                .any(|(source, _)| source == &index.files[file].path);
            for (_, paths) in contexts
                .iter()
                .filter(|(source, _)| !exact || source == &index.files[file].path)
            {
                if let Some(target) = paths
                    .iter()
                    .filter(|(rank, _)| !system || *rank != 0)
                    .find_map(|(_, directory)| {
                        local_path(index, &directory.join(include))
                            .and_then(|path| files.get(path.as_path()).copied())
                    })
                    && target != file
                {
                    edges.push((file, target));
                }
            }
        }
    }

    edges.sort_unstable();
    edges.dedup();
    edges
}

/// Tokenizes literal compilation commands; never expands variables or runs a shell.
fn arguments(command: &serde_json::Value) -> Option<Vec<String>> {
    if let Some(arguments) = command
        .get("arguments")
        .and_then(serde_json::Value::as_array)
    {
        return arguments
            .iter()
            .map(|value| value.as_str().map(str::to_owned))
            .collect();
    }
    let mut result = Vec::new();
    let mut word = String::new();
    let mut quote = None;
    let mut started = false;
    let mut chars = command.get("command")?.as_str()?.chars().peekable();
    while let Some(character) = chars.next() {
        if quote == Some('\'') {
            if character == '\'' {
                quote = None;
            } else {
                word.push(character);
            }
        } else if character == '\\' {
            let next = chars.next()?;
            if next == '\n' {
                continue;
            }
            if quote == Some('"') && !matches!(next, '$' | '`' | '"' | '\\') {
                word.push('\\');
            }
            word.push(next);
            started = true;
        } else if quote == Some('"') {
            if character == '"' {
                quote = None;
            } else if matches!(character, '$' | '`') {
                return None;
            } else {
                word.push(character);
            }
        } else if matches!(character, '\'' | '"') {
            quote = Some(character);
            started = true;
        } else if character.is_whitespace() {
            if started {
                result.push(std::mem::take(&mut word));
                started = false;
            }
        } else if matches!(
            character,
            '$' | '`' | ';' | '&' | '|' | '<' | '>' | '(' | ')' | '#'
        ) {
            return None;
        } else {
            word.push(character);
            started = true;
        }
    }
    if quote.is_some() {
        return None;
    }
    if started {
        result.push(word);
    }
    Some(result)
}
