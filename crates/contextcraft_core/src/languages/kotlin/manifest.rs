//! Literal Gradle project includes, directory mappings, and project dependencies.
//!
//! Supports Kotlin and Groovy DSL statements without evaluating either language.
//! Conditional blocks, composite builds, plugins, and computed paths are not resolved.
//! Files containing `${...}` interpolation, escaped multiline strings, or slashy
//! strings are skipped rather than interpreted.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::PathBuf;

use crate::Config;
use crate::error::Error;
use crate::index::Index;
use crate::languages::local;
use crate::package::{Package, PackageDependency, PackageResolution, Workspace, local_path};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Token<'a> {
    Word(&'a str),
    String(&'a str),
    Symbol(char),
    Newline,
    Other,
}

fn tokens(source: &str) -> Option<Vec<Token<'_>>> {
    let bytes = source.as_bytes();
    let mut tokens = Vec::new();
    let mut offset = 0;
    let mut delimiters = Vec::new();
    while offset < bytes.len() {
        let start = offset;
        match bytes[offset] {
            b'\n' | b';' => {
                tokens.push(Token::Newline);
                offset += 1;
            }
            byte if byte.is_ascii_whitespace() => offset += 1,
            b'/' if bytes.get(offset + 1) == Some(&b'/') => {
                offset += 2;
                while offset < bytes.len() && bytes[offset] != b'\n' {
                    offset += 1;
                }
            }
            b'/' if bytes.get(offset + 1) == Some(&b'*') => {
                offset += 2;
                let mut depth = 1;
                while depth != 0 {
                    match bytes.get(offset..offset + 2)? {
                        b"/*" => {
                            depth += 1;
                            offset += 2;
                        }
                        b"*/" => {
                            depth -= 1;
                            offset += 2;
                        }
                        _ => offset += 1,
                    }
                }
            }
            b'\'' | b'"' => {
                let quote = bytes[offset];
                if bytes
                    .get(offset..offset + 3)
                    .is_some_and(|value| value == [quote; 3])
                {
                    let delimiter = &source[offset..offset + 3];
                    offset += 3;
                    let end = offset + source[offset..].find(delimiter)?;
                    if source[offset..end].contains('\\')
                        || quote == b'"' && source[offset..end].contains("${")
                    {
                        return None;
                    }
                    offset = end + 3;
                    tokens.push(Token::Other);
                    continue;
                }
                offset += 1;
                let content = offset;
                let mut literal = true;
                while *bytes.get(offset)? != quote {
                    if matches!(bytes[offset], b'\n' | b'\r') {
                        return None;
                    }
                    if bytes[offset] == b'\\' {
                        literal = false;
                        offset += 1;
                        bytes.get(offset)?;
                    } else if quote == b'"' && bytes[offset] == b'$' {
                        // Nested string interpolation needs language evaluation; don't tokenize its code.
                        if bytes.get(offset + 1) == Some(&b'{') {
                            return None;
                        }
                        literal = false;
                    }
                    offset += 1;
                }
                tokens.push(if literal {
                    Token::String(&source[content..offset])
                } else {
                    Token::Other
                });
                offset += 1;
            }
            byte if byte.is_ascii_alphanumeric() || byte == b'_' => {
                offset += 1;
                while bytes
                    .get(offset)
                    .is_some_and(|byte| byte.is_ascii_alphanumeric() || *byte == b'_')
                {
                    offset += 1;
                }
                tokens.push(Token::Word(&source[start..offset]));
            }
            b'`' => {
                offset += 1;
                while *bytes.get(offset)? != b'`' {
                    offset += 1;
                }
                offset += 1;
                tokens.push(Token::Other);
            }
            b'/' | b'$' => return None,
            byte if byte.is_ascii() => {
                let symbol = byte as char;
                match symbol {
                    '(' | '[' | '{' => delimiters.push(symbol),
                    ')' | ']' | '}' => {
                        let expected = match symbol {
                            ')' => '(',
                            ']' => '[',
                            _ => '{',
                        };
                        if delimiters.pop() != Some(expected) {
                            return None;
                        }
                    }
                    _ => {}
                }
                tokens.push(Token::Symbol(symbol));
                offset += 1;
            }
            _ => {
                offset += source[offset..].chars().next()?.len_utf8();
                tokens.push(Token::Other);
            }
        }
    }
    delimiters.is_empty().then_some(tokens)
}

fn statements<'a, 'source>(tokens: &'a [Token<'source>]) -> Vec<&'a [Token<'source>]> {
    let mut result = Vec::new();
    let mut depth = 0;
    let mut start = 0;
    for (offset, token) in tokens.iter().enumerate() {
        match token {
            Token::Symbol('(' | '[' | '{') => depth += 1,
            Token::Symbol(')' | ']' | '}') => depth -= 1,
            Token::Newline
                if depth == 0
                    && tokens.get(offset + 1) != Some(&Token::Symbol('{'))
                    && !matches!(
                        tokens.get(offset.wrapping_sub(1)),
                        Some(Token::Symbol(',' | '=' | '.'))
                    ) =>
            {
                if start < offset {
                    result.push(&tokens[start..offset]);
                }
                start = offset + 1;
            }
            _ => {}
        }
    }
    if start < tokens.len() {
        result.push(&tokens[start..]);
    }
    result
}

fn flat<'a>(tokens: &[Token<'a>]) -> Vec<Token<'a>> {
    tokens
        .iter()
        .copied()
        .filter(|token| *token != Token::Newline)
        .collect()
}

fn project_path(value: &str) -> Option<String> {
    if value == ":" {
        return Some(value.into());
    }
    let value = value.strip_prefix(':').unwrap_or(value);
    value
        .split(':')
        .all(|part| !part.is_empty() && !matches!(part, "." | "..") && !part.contains(['/', '\\']))
        .then(|| format!(":{value}"))
}

fn strings<'a>(tokens: &[Token<'a>]) -> Option<Vec<&'a str>> {
    let tokens = match tokens {
        [Token::Symbol('('), args @ .., Token::Symbol(')')] => args,
        args => args,
    };
    let mut values = Vec::new();
    let mut chunks = tokens.chunks(2).peekable();
    while let Some(chunk) = chunks.next() {
        match chunk {
            [Token::String(value), Token::Symbol(',')] => values.push(*value),
            [Token::String(value)] if chunks.peek().is_none() => values.push(*value),
            _ => return None,
        }
    }
    Some(values)
}

struct Settings {
    manifest: PathBuf,
    root: PathBuf,
    name: Option<String>,
    projects: BTreeMap<String, PathBuf>,
}

fn settings(index: &Index, config: &Config) -> Result<Vec<Settings>, Error> {
    let mut documents = BTreeMap::new();
    for (_, file) in index.files.iter().filter(|(_, file)| {
        file.path
            .file_name()
            .is_some_and(|name| name == "settings.gradle" || name == "settings.gradle.kts")
    }) {
        let root = file.path.parent().unwrap();
        // Gradle prefers the Groovy settings file when both DSL variants exist.
        if documents.contains_key(root) {
            continue;
        }
        let mut document = Settings {
            manifest: file.path.clone(),
            root: root.to_path_buf(),
            name: None,
            projects: BTreeMap::from([(":".into(), root.to_path_buf())]),
        };
        if let Some(source) = local::read(index, &file.path, config)?
            && let Some(tokens) = tokens(&source)
        {
            let mut overrides = HashMap::new();
            for statement in statements(&tokens) {
                let statement = flat(statement);
                match statement.as_slice() {
                    [Token::Word("include"), args @ ..] => {
                        if let Some(names) = strings(args) {
                            for name in names {
                                if let Some(name) = project_path(name)
                                    && name != ":"
                                {
                                    let mut project = name.as_str();
                                    while !project.is_empty() {
                                        let path = root.join(
                                            project.trim_start_matches(':').replace(':', "/"),
                                        );
                                        document.projects.entry(project.to_owned()).or_insert(path);
                                        project = project.rsplit_once(':').unwrap().0;
                                    }
                                }
                            }
                        }
                    }
                    [
                        Token::Word("rootProject"),
                        Token::Symbol('.'),
                        Token::Word("name"),
                        Token::Symbol('='),
                        Token::String(name),
                    ] => document.name = Some((*name).into()),
                    [
                        Token::Word("project"),
                        Token::Symbol('('),
                        Token::String(name),
                        Token::Symbol(')'),
                        Token::Symbol('.'),
                        Token::Word("projectDir"),
                        Token::Symbol('='),
                        expression @ ..,
                    ] => {
                        if let Some(name) = project_path(name) {
                            let path = match expression {
                                [
                                    Token::Word("file"),
                                    Token::Symbol('('),
                                    Token::String(path),
                                    Token::Symbol(')'),
                                ] => Some(root.join(path)),
                                _ => None,
                            };
                            overrides.insert(name, path);
                        }
                    }
                    _ => {}
                }
            }
            document.projects = document
                .projects
                .into_iter()
                .filter_map(|(name, path)| {
                    let path = overrides.get(&name).map_or(Some(path), Clone::clone)?;
                    Some((name, local_path(index, &path)?))
                })
                .collect();
        }
        documents.insert(root.to_path_buf(), document);
    }
    Ok(documents.into_values().collect())
}

fn dependencies(source: &str) -> Vec<String> {
    let Some(tokens) = tokens(source) else {
        return Vec::new();
    };
    let mut dependencies = Vec::new();
    for statement in statements(&tokens) {
        let Some(open) = statement
            .iter()
            .position(|token| *token == Token::Symbol('{'))
        else {
            continue;
        };
        if flat(&statement[..open]) != [Token::Word("dependencies")] {
            continue;
        }
        let [body @ .., Token::Symbol('}')] = &statement[open + 1..] else {
            continue;
        };
        for declaration in statements(body) {
            let declaration = flat(declaration);
            let [Token::Word(configuration), args @ ..] = declaration.as_slice() else {
                continue;
            };
            if !matches!(
                *configuration,
                "api"
                    | "implementation"
                    | "compileOnly"
                    | "compileOnlyApi"
                    | "runtimeOnly"
                    | "testImplementation"
                    | "testCompileOnly"
                    | "testRuntimeOnly"
                    | "androidTestImplementation"
                    | "testFixturesApi"
                    | "testFixturesImplementation"
                    | "kapt"
                    | "ksp"
            ) {
                continue;
            }
            let args = match args {
                [Token::Symbol('('), args @ .., Token::Symbol(')')] => args,
                args => args,
            };
            let name = match args {
                [
                    Token::Word("project"),
                    Token::Symbol('('),
                    Token::String(name),
                    Token::Symbol(')'),
                ]
                | [
                    Token::Word("project"),
                    Token::Symbol('('),
                    Token::Word("path"),
                    Token::Symbol('=' | ':'),
                    Token::String(name),
                    Token::Symbol(')'),
                ] => project_path(name).map(|_| (*name).to_owned()),
                _ => None,
            };
            if let Some(name) = name {
                dependencies.push(name);
            }
        }
    }
    dependencies.sort_unstable();
    dependencies.dedup();
    dependencies
}

/// Discovers Gradle build roots and literal included projects before file ownership is assigned.
///
/// Supports `include`, `rootProject.name`, and `project(...).projectDir = file(...)`.
/// Computed directory overrides are not replaced with guessed default directories.
///
/// # Errors
///
/// Returns an error if settings cannot be read, are not UTF-8, or multiple project
/// names in one settings file map to the same local directory. Oversized files are skipped.
pub fn packages(index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
    let mut packages: BTreeMap<_, _> =
        local::discover(index, "kotlin", &[], &["build.gradle", "build.gradle.kts"])
            .into_iter()
            .map(|package| (package.root.clone(), package))
            .collect();
    for document in settings(index, config)? {
        let mut seen = HashSet::new();
        for (name, root) in document.projects {
            if !seen.insert(root.clone()) {
                return Err(Error::Manifest {
                    path: document.manifest.clone(),
                    message: "Gradle projects sharing a directory have ambiguous file ownership"
                        .into(),
                });
            }
            let package = packages.entry(root.clone()).or_insert_with(|| Package {
                root,
                name: None,
                language: Some("kotlin"),
                manifests: Vec::new(),
                targets: Vec::new(),
                dependencies: Vec::new(),
            });
            if name == ":" {
                package.name = document.name.clone();
                package.manifests.push(document.manifest.clone());
            } else {
                package.name = name.rsplit(':').next().map(str::to_owned);
            }
        }
    }
    for package in packages.values_mut() {
        package.manifests.sort();
        package.manifests.dedup();
    }
    Ok(packages.into_values().collect())
}

/// Resolves literal Gradle project dependencies and records explicit build membership.
///
/// Only known dependency configurations in top-level `dependencies` blocks are
/// supported. Workspace membership alone does not grant cross-project visibility.
///
/// # Errors
///
/// Returns an error if settings or build files cannot be read or are not UTF-8.
/// Oversized files and unsupported expressions are skipped without executing Gradle.
pub fn discover(index: &Index, config: &Config) -> Result<PackageResolution, Error> {
    let mut resolution = PackageResolution::default();
    let roots: HashMap<_, _> = index
        .packages
        .iter()
        .filter(|(_, package)| package.language == Some("kotlin"))
        .map(|(id, package)| (package.root.as_path(), id))
        .collect();
    let mut workspaces = Vec::new();
    for document in settings(index, config)? {
        let projects: BTreeMap<_, _> = document
            .projects
            .into_iter()
            .filter_map(|(name, root)| roots.get(root.as_path()).map(|&id| (name, id)))
            .collect();
        let mut members: Vec<_> = projects.values().copied().collect();
        members.sort_unstable();
        members.dedup();
        resolution.workspaces.push(Workspace {
            root: document.root,
            language: "kotlin",
            members,
        });
        workspaces.push(projects);
    }
    for &id in roots.values() {
        let mut package = index.packages[id].clone();
        package.targets = index
            .files
            .iter()
            .filter(|(_, file)| file.package_id == id && file.language == Some("kotlin"))
            .map(|(id, _)| id)
            .collect();
        if let Some(manifest) = package.manifests.iter().find(|path| {
            path.file_name()
                .is_some_and(|name| name == "build.gradle" || name == "build.gradle.kts")
        }) && let Some(source) = local::read(index, manifest, config)?
        {
            for alias in dependencies(&source) {
                let candidates: HashSet<_> = workspaces
                    .iter()
                    .flat_map(|projects| {
                        projects.iter().filter_map(|(name, &member)| {
                            if member != id {
                                return None;
                            }
                            let path = if alias.starts_with(':') {
                                alias.clone()
                            } else {
                                format!("{}:{alias}", name.trim_end_matches(':'))
                            };
                            projects.get(&path).copied()
                        })
                    })
                    .collect();
                if candidates.len() == 1 {
                    let target = *candidates.iter().next().unwrap();
                    if target != id {
                        package.dependencies.push(PackageDependency {
                            alias,
                            package: target,
                        });
                    }
                }
            }
        }
        resolution.packages.insert(id, package);
    }
    Ok(resolution)
}
