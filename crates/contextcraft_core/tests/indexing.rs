mod common;

use contextcraft_core::Config;
use contextcraft_core::error::Error;
use contextcraft_core::index::Indexer;

#[test]
fn scanning_respects_ignore_rules_exclusions_and_hidden_metadata() {
    let root = common::fixture(&[
        (".gitignore", "ignored.txt\n"),
        ("ignored.txt", "ignored"),
        ("visible.txt", "visible"),
        ("omit.txt", "excluded"),
        (".python-version", "3.12"),
        (".secret", "hidden"),
        (".hidden/source.py", "pass"),
        ("node_modules/dependency.js", "export const value = 1;"),
    ]);

    for respect_gitignore in [true, false] {
        let config = Config {
            respect_gitignore,
            exclude_patterns: vec!["omit.txt".into()],
            ..Config::default()
        };
        let index = Indexer::new().index(root.path(), &config).unwrap();
        let paths: Vec<_> = index
            .files
            .iter()
            .map(|(_, file)| file.path.to_str().unwrap())
            .collect();

        assert!(paths.contains(&"visible.txt"));
        assert!(paths.contains(&".python-version"));
        assert_eq!(paths.contains(&"ignored.txt"), !respect_gitignore);
        assert!(!paths.contains(&"omit.txt"));
        assert!(!paths.contains(&".secret"));
        assert!(
            !paths
                .iter()
                .any(|path| path.starts_with(".hidden") || path.starts_with("node_modules"))
        );
        assert!(paths.windows(2).all(|pair| pair[0] < pair[1]));
    }
}

#[test]
fn nested_packages_own_their_sources_and_manifests() {
    let root = common::fixture(&[
        ("Cargo.toml", "[workspace]\nmembers = ['crates/*']\n"),
        (
            "crates/a/Cargo.toml",
            "[package]\nname = 'a'\nversion = '0.1.0'\n",
        ),
        ("crates/a/src/lib.rs", "pub fn a() {}"),
        (
            "crates/b/Cargo.toml",
            "[package]\nname = 'b'\nversion = '0.1.0'\n",
        ),
        ("crates/b/src/lib.rs", "pub fn b() {}"),
        ("notes.txt", "unowned"),
    ]);
    let index = Indexer::new()
        .index(root.path(), &Config::default())
        .unwrap();
    assert_eq!(index.workspaces.len(), 1);
    assert_eq!(index.workspaces[0].members.len(), 2);

    for (_, file) in index.files.iter() {
        let package = &index.packages[file.package_id];
        let path = file
            .path
            .to_string_lossy()
            .replace(std::path::MAIN_SEPARATOR, "/");
        if path.starts_with("crates/a/") {
            assert_eq!(package.name.as_deref(), Some("a"));
        } else if path.starts_with("crates/b/") {
            assert_eq!(package.name.as_deref(), Some("b"));
        } else if path == "notes.txt" {
            assert!(package.root.as_os_str().is_empty());
            assert!(
                package
                    .manifests
                    .iter()
                    .any(|path| path == std::path::Path::new("Cargo.toml"))
            );
        }
    }
}

#[test]
fn invalid_roots_patterns_and_manifests_return_errors() {
    let root = common::fixture(&[("file.txt", "content")]);
    let indexer = Indexer::new();
    let config = Config::default();

    assert!(matches!(
        indexer.index(root.path().join("missing"), &config),
        Err(Error::Io { .. })
    ));
    assert!(matches!(
        indexer.index(root.path().join("file.txt"), &config),
        Err(Error::NotADirectory(_))
    ));
    let invalid_pattern = Config {
        exclude_patterns: vec!["[".into()],
        ..config.clone()
    };
    assert!(matches!(
        indexer.index(root.path(), &invalid_pattern),
        Err(Error::Ignore(_))
    ));

    std::fs::write(root.path().join("Cargo.toml"), "[package\n").unwrap();
    assert!(matches!(
        indexer.index(root.path(), &config),
        Err(Error::Manifest { .. })
    ));
}

#[cfg(unix)]
#[test]
fn scanning_does_not_follow_file_or_directory_symlinks() {
    use std::os::unix::fs::symlink;

    let root = common::fixture(&[("real/source.txt", "content")]);
    let outside = common::fixture(&[("external.txt", "external")]);
    symlink(
        root.path().join("real/source.txt"),
        root.path().join("alias.txt"),
    )
    .unwrap();
    symlink(outside.path(), root.path().join("outside")).unwrap();
    let index = Indexer::new()
        .index(root.path(), &Config::default())
        .unwrap();
    let paths: Vec<_> = index
        .files
        .iter()
        .map(|(_, file)| file.path.to_string_lossy())
        .collect();

    assert_eq!(paths, ["real/source.txt"]);
}
