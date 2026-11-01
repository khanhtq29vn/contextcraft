//! Discover files, package ownership, and local workspace relationships.

use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::{Path, PathBuf};

use ignore::WalkBuilder;
use ignore::overrides::OverrideBuilder;
use la_arena::{Arena, Idx};

use crate::Config;
use crate::error::Error;
use crate::languages::{
    Language, bash::Bash, c::C, cmake::CMake, cpp::Cpp, csharp::CSharp, css::Css,
    detect::LanguageDetector, dockerfile::Dockerfile, elixir::Elixir, go::Go, graphql::Graphql,
    hcl::Hcl, html::Html, java::Java, javascript::JavaScript, json::Json, just::Just,
    kotlin::Kotlin, lua::Lua, make::Make, markdown::Markdown, php::Php, protobuf::Protobuf,
    python::Python, r::R, rst::Rst, ruby::Ruby, rust::Rust, scala::Scala, scss::Scss, sql::Sql,
    svelte::Svelte, swift::Swift, toml::Toml, typescript::TypeScript, vue::Vue, yaml::Yaml,
    zig::Zig,
};
use crate::package::{Package, Workspace};

/// File identifier within one [`Index::files`] arena. Not portable across indexes.
pub type FileId = Idx<File>;
/// Package identifier within one [`Index::packages`] arena.
pub type PackageId = Idx<Package>;

/// One repository file and its package and language assignments.
#[derive(Debug)]
pub struct File {
    /// File path relative to [`Index::root`].
    pub path: PathBuf,
    /// Owning package, or the index's fallback package when none is detected.
    pub package_id: PackageId,
    /// Registered language ID, or `None` when no supported language is detected.
    pub language: Option<&'static str>,
}

/// Repository-relative files, packages, and detected language implementations.
///
/// When editing fields, keep arena IDs, package ownership, and language IDs
/// consistent. Rebuild downstream analysis after changing indexed data.
#[derive(Debug)]
pub struct Index {
    /// Canonical absolute repository directory.
    pub root: PathBuf,
    /// Files in sorted path order. Their arena IDs link all pipeline stages.
    pub files: Arena<File>,
    /// Detected packages, including a fallback package for unowned files.
    pub packages: Arena<Package>,
    /// Workspace memberships discovered from local manifests.
    pub workspaces: Vec<Workspace>,
    /// Detected language implementations keyed by their IDs.
    pub languages: HashMap<&'static str, Box<dyn Language>>,
}

impl Index {
    fn assign_packages(&mut self, fallback: PackageId, languages: &[Box<dyn Language>]) {
        let package_languages: HashMap<_, _> = languages
            .iter()
            .map(|language| (language.id(), language.package_language()))
            .collect();
        let mut by_language = HashMap::new();
        let mut by_root: HashMap<_, Vec<_>> = HashMap::new();
        let mut by_manifest = HashMap::new();

        for (id, package) in self.packages.iter() {
            if let Some(language) = package.language {
                by_language.insert((package.root.as_path(), language), id);
                by_root.entry(package.root.as_path()).or_default().push(id);
            }

            for manifest in &package.manifests {
                by_manifest.insert(manifest.as_path(), id);
            }
        }

        for (_, file) in self.files.iter_mut() {
            file.package_id = if let Some(&id) = by_manifest.get(file.path.as_path()) {
                id
            } else if let Some(language) = file.language {
                let language = package_languages[language];
                file.path
                    .parent()
                    .unwrap()
                    .ancestors()
                    .find_map(|parent| by_language.get(&(parent, language)).copied())
                    .unwrap_or(fallback)
            } else {
                file.path
                    .parent()
                    .unwrap()
                    .ancestors()
                    .find_map(|parent| by_root.get(parent))
                    .and_then(|ids| (ids.len() == 1).then_some(ids[0]))
                    .unwrap_or(fallback)
            };
        }
    }
}

/// Discovers supported languages and local package relationships.
#[derive(Debug, Default)]
pub struct Indexer;

impl Indexer {
    /// Creates a repository indexer.
    pub fn new() -> Self {
        Self
    }

    /// Scans a directory and resolves package metadata for detected languages.
    ///
    /// # Errors
    ///
    /// Returns an error if the root is not a directory, scanning fails, an
    /// exclusion is invalid, or package metadata cannot be read or parsed.
    pub fn index(&self, root: impl AsRef<Path>, config: &Config) -> Result<Index, Error> {
        let languages: Vec<Box<dyn Language>> = vec![
            Box::new(Python::default()),
            Box::new(Rust::default()),
            Box::new(Go::default()),
            Box::new(C),
            Box::new(Cpp),
            Box::new(JavaScript),
            Box::new(TypeScript::default()),
            Box::new(TypeScript::tsx()),
            Box::new(Vue),
            Box::new(Svelte),
            Box::new(Markdown),
            Box::new(Html),
            Box::new(Toml),
            Box::new(Yaml),
            Box::new(Json),
            Box::new(Bash),
            Box::new(CSharp),
            Box::new(Lua),
            Box::new(Ruby),
            Box::new(Elixir),
            Box::new(Java),
            Box::new(Kotlin),
            Box::new(Php),
            Box::new(R),
            Box::new(Zig),
            Box::new(Scala),
            Box::new(Swift),
            Box::new(Graphql),
            Box::new(Hcl),
            Box::new(Dockerfile::default()),
            Box::new(Make),
            Box::new(Just),
            Box::new(Rst),
            Box::new(Css),
            Box::new(Scss),
            Box::new(Protobuf),
            Box::new(CMake),
            Box::new(Sql),
        ];

        let root = root.as_ref();
        let root = root.canonicalize().map_err(|source| Error::Io {
            path: root.to_path_buf(),
            source,
        })?;

        if !root.is_dir() {
            return Err(Error::NotADirectory(root));
        }

        let paths = scan_files(&root, &languages, config)?;

        let mut packages = Arena::new();
        let fallback = packages.alloc(Package {
            root: PathBuf::new(),
            name: None,
            language: None,
            manifests: Vec::new(),
            targets: Vec::new(),
            dependencies: Vec::new(),
        });

        let mut files = Arena::with_capacity(paths.len());

        let detector = LanguageDetector::new(&languages);

        for path in paths {
            let language = detector.detect(&path, || {
                let mut bytes = Vec::new();
                std::fs::File::open(root.join(&path))
                    .ok()?
                    .take((config.max_file_size_bytes.get() as u64).saturating_add(1))
                    .read_to_end(&mut bytes)
                    .ok()?;
                (bytes.len() <= config.max_file_size_bytes.get()).then_some(bytes)
            });

            files.alloc(File {
                path,
                package_id: fallback,
                language,
            });
        }

        let mut index = Index {
            root,
            files,
            packages,
            workspaces: Vec::new(),
            languages: HashMap::new(),
        };

        // Allocate every language's packages before linking dependencies between them.
        let mut detected = Vec::new();
        let mut discovered = HashSet::new();

        for language in languages {
            let packages = if discovered.insert(language.package_language()) {
                language.discover_packages(&index, config)?
            } else {
                Vec::new()
            };
            let has_sources = index
                .files
                .iter()
                .any(|(_, file)| file.language == Some(language.id()));

            if has_sources || !packages.is_empty() {
                for package in packages {
                    index.packages.alloc(package);
                }

                detected.push(language);
            }
        }

        index.assign_packages(fallback, &detected);

        let mut resolved = HashSet::new();
        for mut language in detected {
            let resolution = if resolved.insert(language.package_language()) {
                language.resolve_packages(&index, config)?
            } else {
                crate::package::PackageResolution::default()
            };

            for (id, package) in resolution.packages {
                index.packages[id] = package;
            }

            index.workspaces.extend(resolution.workspaces);
            index.languages.insert(language.id(), language);
        }

        Ok(index)
    }
}

fn scan_files(
    root: &Path,
    languages: &[Box<dyn Language>],
    config: &Config,
) -> Result<Vec<PathBuf>, Error> {
    let mut overrides = OverrideBuilder::new(root);

    for pattern in languages
        .iter()
        .flat_map(|language| language.ignore_patterns())
    {
        overrides.add(pattern)?;
    }

    for pattern in &config.exclude_patterns {
        overrides.add(&format!("!{pattern}"))?;
    }

    let hidden_metadata: HashSet<_> = languages
        .iter()
        .flat_map(|language| language.package_metadata_files().iter().copied())
        .filter(|name| name.starts_with('.'))
        .collect();
    let walker = WalkBuilder::new(root)
        .hidden(false)
        .filter_entry(move |entry| {
            entry.depth() == 0
                || entry.file_name().to_str().is_none_or(|name| {
                    !name.starts_with('.')
                        || (entry.file_type().is_some_and(|kind| kind.is_file())
                            && hidden_metadata.contains(name))
                })
        })
        .require_git(false)
        .git_ignore(config.respect_gitignore)
        .git_global(config.respect_gitignore)
        .git_exclude(config.respect_gitignore)
        .follow_links(false)
        .overrides(overrides.build()?)
        .build();

    let mut paths = Vec::new();

    for entry in walker {
        let entry = entry?;

        if let Some(error) = entry.error() {
            return Err(error.clone().into());
        }

        if entry.file_type().is_some_and(|kind| kind.is_file()) {
            paths.push(entry.path().strip_prefix(root).unwrap().to_path_buf());
        }
    }

    let ignored_directories: HashSet<_> = languages
        .iter()
        .flat_map(|language| language.ignored_directories(&paths))
        .collect();
    if !ignored_directories.is_empty() {
        paths.retain(|path| {
            !path
                .ancestors()
                .any(|parent| ignored_directories.contains(parent))
        });
    }
    paths.sort();

    Ok(paths)
}
