---
title: "contextcraft-ai-core::index"
description: "Discover files, package ownership, and local workspace relationships."
editUrl: false
sidebar:
  order: 11
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Discover files, package ownership, and local workspace relationships.

## Structs

### <span id="struct.File"></span><code style="font-size: 0.85em">struct File</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

One repository file and its package and language assignments.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `path` | `PathBuf` | File path relative to `Index::root`. |
| `package_id` | `PackageId` | Owning package, or the index's fallback package when none is detected. |
| `language` | `Option<&'static str>` | Registered language ID, or `None` for an unsupported filename or extension. |

### <span id="struct.Index"></span><code style="font-size: 0.85em">struct Index</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Repository-relative files, packages, and detected language implementations.

When editing fields, keep arena IDs, package ownership, and language IDs
consistent. Rebuild downstream analysis after changing indexed data.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Canonical absolute repository directory. |
| `files` | `Arena<File>` | Files in sorted path order. Their arena IDs link all pipeline stages. |
| `packages` | `Arena<Package>` | Detected packages, including a fallback package for unowned files. |
| `workspaces` | `Vec<Workspace>` | Workspace memberships discovered from local manifests. |
| `languages` | `HashMap<&'static str, Box<dyn Language>>` | Detected language implementations keyed by their IDs. |

### <span id="struct.Indexer"></span><code style="font-size: 0.85em">struct Indexer</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Discovers supported languages and local package relationships.

#### Methods

##### <span id="Indexer.new"></span><code>new</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn new() -> Self
```

Creates a repository indexer.

<details>
<summary>Source</summary>

```rust
    pub fn new() -> Self {
        Self
    }
```

</details>

##### <span id="Indexer.index"></span><code>index</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn index(
    &self,
    root: impl AsRef<Path>,
    config: &Config,
) -> Result<Index, Error>
```

Scans a directory and resolves package metadata for detected languages.

**Errors:**

Returns an error if the root is not a directory, scanning fails, an
exclusion is invalid, or package metadata cannot be read or parsed.

<details>
<summary>Source</summary>

```rust
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
            Box::new(Kotlin),
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

        for path in paths {
            let language = languages
                .iter()
                .find(|language| {
                    path.file_name()
                        .and_then(|name| name.to_str())
                        .is_some_and(|name| language.matches_filename(name))
                })
                .or_else(|| {
                    languages.iter().find(|language| {
                        language.file_extensions().iter().any(|extension| {
                            path.extension()
                                .is_some_and(|suffix| suffix == extension.trim_start_matches('.'))
                        })
                    })
                })
                .map(|language| language.id());

            let language = if language == Some("c")
                && path.extension().is_some_and(|extension| extension == "h")
            {
                header_language(&root.join(&path), config).or(language)
            } else {
                language
            };

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

        for language in languages {
            let packages = language.discover_packages(&index, config)?;
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

        for mut language in detected {
            let resolution = language.resolve_packages(&index, config)?;

            for (id, package) in resolution.packages {
                index.packages[id] = package;
            }

            index.workspaces.extend(resolution.workspaces);
            index.languages.insert(language.id(), language);
        }

        Ok(index)
    }
```

</details>

## Type aliases

| Name | Type | Description |
|------|------|-------------|
| <span id="type.FileId"></span>`FileId` | `Idx<File>` | File identifier within one `Index::files` arena. Not portable across indexes. |
| <span id="type.PackageId"></span>`PackageId` | `Idx<Package>` | Package identifier within one `Index::packages` arena. |
