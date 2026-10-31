mod common;

use std::collections::BTreeSet;

use contextcraft_core::Config;
use contextcraft_core::index::{FileId, Indexer};
use contextcraft_core::languages::{Language, bash::Bash, css::Css, hcl::Hcl, yaml::Yaml};
use contextcraft_core::repo::RepositoryReader;
use la_arena::RawIdx;

#[test]
fn all_registered_languages_compile_queries_and_analyze_empty_sources() {
    let filenames = [
        "empty.py",
        "empty.rs",
        "empty.go",
        "empty.c",
        "empty.cpp",
        "empty.js",
        "empty.ts",
        "empty.tsx",
        "empty.vue",
        "empty.svelte",
        "empty.md",
        "empty.html",
        "empty.toml",
        "empty.yaml",
        "empty.json",
        "empty.sh",
        "empty.cs",
        "empty.lua",
        "empty.rb",
        "empty.ex",
        "empty.kt",
        "empty.zig",
        "empty.scala",
        "empty.swift",
        "empty.graphql",
        "empty.tf",
        "Dockerfile",
        "Makefile",
        "justfile",
        "empty.rst",
        "empty.css",
        "empty.scss",
        "empty.proto",
        "empty.cmake",
        "empty.sql",
    ];
    let files: Vec<_> = filenames.iter().map(|&name| (name, "")).collect();
    let root = common::fixture(&files);
    let config = Config::default();
    let index = Indexer::new().index(root.path(), &config).unwrap();
    let expected: BTreeSet<_> = [
        "python",
        "rust",
        "go",
        "c",
        "cpp",
        "javascript",
        "typescript",
        "tsx",
        "vue",
        "svelte",
        "markdown",
        "html",
        "toml",
        "yaml",
        "json",
        "bash",
        "csharp",
        "lua",
        "ruby",
        "elixir",
        "kotlin",
        "zig",
        "scala",
        "swift",
        "graphql",
        "hcl",
        "dockerfile",
        "make",
        "just",
        "rst",
        "css",
        "scss",
        "protobuf",
        "cmake",
        "sql",
    ]
    .into_iter()
    .collect();

    assert_eq!(
        index.languages.keys().copied().collect::<BTreeSet<_>>(),
        expected
    );
    for language in index.languages.values() {
        language
            .query()
            .unwrap_or_else(|error| panic!("{} query: {error}", language.id()));
    }
    let repository = RepositoryReader::new().read(&index, &config).unwrap();
    assert_eq!(repository.sources.iter().count(), filenames.len());
    assert!(
        repository
            .sources
            .values()
            .all(|source| source.analysis.is_some())
    );
}

#[test]
fn shared_data_renderer_keeps_representative_language_outlines_readable() {
    let examples: [(&dyn Language, &str, &str, &str); 4] = [
        (
            &Yaml,
            "# Service\nservice:\n  name: api\n  enabled: true\n",
            "name: api",
            "enabled: true",
        ),
        (
            &Hcl,
            "# Service\nresource \"service\" \"api\" {\n  name = \"api\"\n  enabled = true\n}\n",
            "name = \"api\"",
            "enabled = true",
        ),
        (
            &Css,
            "/* Service */\n.api {\n  color: red;\n  display: block;\n}\n",
            "color: red;",
            "display: block;",
        ),
        (
            &Bash,
            "# Service\nsource ./env.sh\nstart() {\n  echo payload\n}\n",
            "source ./env.sh",
            "start()",
        ),
    ];

    for (language, source, first, second) in examples {
        let mut parser = tree_sitter::Parser::new();
        let query = language.query().unwrap();
        let state = language.create_analysis();
        let analysis = language
            .analyze(
                FileId::from_raw(RawIdx::from_u32(0)),
                &mut parser,
                &query,
                source.as_bytes(),
                state.as_ref(),
            )
            .unwrap();
        let skeleton = language.render_skel(source, &analysis);

        assert!(skeleton.contains(first), "{}: {skeleton}", language.id());
        assert!(skeleton.contains(second), "{}: {skeleton}", language.id());
        if language.id() == "bash" {
            assert!(!skeleton.contains("echo payload"));
        }
    }
}
