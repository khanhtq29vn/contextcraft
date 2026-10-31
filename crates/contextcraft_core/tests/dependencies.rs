mod common;

use std::collections::BTreeSet;
use std::path::Path;

use contextcraft_core::Config;
use contextcraft_core::graph::Graph;
use contextcraft_core::index::Indexer;
use contextcraft_core::repo::RepositoryReader;

fn edges(root: &Path) -> BTreeSet<(String, String)> {
    let config = Config::default();
    let index = Indexer::new().index(root, &config).unwrap();
    let repository = RepositoryReader::new().read(&index, &config).unwrap();
    let graph = Graph::new(&index, &repository);

    graph
        .dependencies
        .all_edges()
        .map(|(from, to, ())| {
            assert_ne!(from, to);
            let path = |file: contextcraft_core::index::FileId| {
                index.files[file]
                    .path
                    .to_string_lossy()
                    .replace(std::path::MAIN_SEPARATOR, "/")
            };
            (path(from), path(to))
        })
        .collect()
}

fn expected(pairs: &[(&str, &str)]) -> BTreeSet<(String, String)> {
    pairs
        .iter()
        .map(|(from, to)| (from.to_string(), to.to_string()))
        .collect()
}

#[test]
fn cargo_workspaces_respect_normal_dev_and_build_dependency_visibility() {
    let root = common::fixture(&[
        (
            "Cargo.toml",
            "[workspace]\nmembers = ['app', 'shared', 'dev-only', 'build-tool']\nresolver = '3'\n",
        ),
        (
            "app/Cargo.toml",
            "[package]\nname = 'app'\nversion = '0.1.0'\nedition = '2024'\n[dependencies]\nshared = { path = '../shared' }\n[dev-dependencies]\ndev-only = { path = '../dev-only' }\n[build-dependencies]\nbuild-tool = { path = '../build-tool' }\n",
        ),
        (
            "app/src/lib.rs",
            "pub mod auth;\nuse shared::Shared;\nuse dev_only::Dev;\nuse build_tool::Tool;\n",
        ),
        ("app/src/auth.rs", "pub fn authenticate() {}\n"),
        ("app/tests/integration.rs", "use dev_only::Dev;\n"),
        ("app/build.rs", "use build_tool::Tool;\nfn main() {}\n"),
        (
            "shared/Cargo.toml",
            "[package]\nname = 'shared'\nversion = '0.1.0'\n",
        ),
        ("shared/src/lib.rs", "pub struct Shared;\n"),
        (
            "dev-only/Cargo.toml",
            "[package]\nname = 'dev-only'\nversion = '0.1.0'\n",
        ),
        ("dev-only/src/lib.rs", "pub struct Dev;\n"),
        (
            "build-tool/Cargo.toml",
            "[package]\nname = 'build-tool'\nversion = '0.1.0'\n",
        ),
        ("build-tool/src/lib.rs", "pub struct Tool;\n"),
    ]);

    assert_eq!(
        edges(root.path()),
        expected(&[
            ("app/src/lib.rs", "app/src/auth.rs"),
            ("app/src/lib.rs", "shared/src/lib.rs"),
            ("app/tests/integration.rs", "dev-only/src/lib.rs"),
            ("app/build.rs", "build-tool/src/lib.rs"),
        ])
    );
}

#[test]
fn python_relative_import_cycles_include_initializers_but_not_unrelated_packages() {
    let root = common::fixture(&[
        (
            "pyproject.toml",
            "[project]\nname = 'fixture'\nversion = '0.1.0'\n",
        ),
        ("src/pkg/__init__.py", ""),
        (
            "src/pkg/a.py",
            "from . import b\nimport nonexistent\nimport isolated\n",
        ),
        ("src/pkg/b.py", "from . import a\n"),
        (
            "other/pyproject.toml",
            "[project]\nname = 'other'\nversion = '0.1.0'\n",
        ),
        ("other/src/isolated.py", "value = 1\n"),
    ]);

    assert_eq!(
        edges(root.path()),
        expected(&[
            ("src/pkg/a.py", "src/pkg/__init__.py"),
            ("src/pkg/a.py", "src/pkg/b.py"),
            ("src/pkg/b.py", "src/pkg/__init__.py"),
            ("src/pkg/b.py", "src/pkg/a.py"),
        ])
    );
}

#[test]
fn typescript_resolves_aliases_and_declared_workspace_exports() {
    let root = common::fixture(&[
        (
            "package.json",
            r#"{"private":true,"workspaces":["packages/*"]}"#,
        ),
        (
            "packages/app/package.json",
            r#"{"name":"app","dependencies":{"@fixture/shared":"workspace:*"}}"#,
        ),
        (
            "packages/app/tsconfig.json",
            r#"{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}"#,
        ),
        (
            "packages/app/src/main.ts",
            "import { ready } from '@/util';\nimport { shared } from '@fixture/shared';\nimport missing from 'not-installed';\n",
        ),
        ("packages/app/src/util.ts", "export const ready = true;\n"),
        (
            "packages/shared/package.json",
            r#"{"name":"@fixture/shared","exports":{".":"./src/index.ts"}}"#,
        ),
        (
            "packages/shared/src/index.ts",
            "export const shared = true;\n",
        ),
    ]);

    assert_eq!(
        edges(root.path()),
        expected(&[
            ("packages/app/src/main.ts", "packages/app/tsconfig.json"),
            ("packages/app/src/main.ts", "packages/app/src/util.ts"),
            ("packages/app/src/main.ts", "packages/shared/src/index.ts"),
            ("packages/app/src/util.ts", "packages/app/tsconfig.json"),
        ])
    );
}

#[test]
fn javascript_relative_import_cycles_are_deduplicated_and_unknown_imports_are_ignored() {
    let root = common::fixture(&[
        (
            "a.js",
            "import './b.js';\nimport './b.js';\nimport './missing.js';\nimport './a.js';\n",
        ),
        ("b.js", "import './a.js';\n"),
    ]);

    assert_eq!(
        edges(root.path()),
        expected(&[("a.js", "b.js"), ("b.js", "a.js")])
    );
}
