use contextcraft_core::index::FileId;
use contextcraft_core::languages::{Language, json::Json, rust::Rust, toml::Toml};
use contextcraft_core::repo::Analysis;
use la_arena::RawIdx;

fn analyze(language: &dyn Language, source: &str) -> Analysis {
    let mut parser = tree_sitter::Parser::new();
    let query = language.query().unwrap();

    language
        .analyze(
            FileId::from_raw(RawIdx::from_u32(0)),
            &mut parser,
            &query,
            source.as_bytes(),
            &(),
        )
        .unwrap()
}

#[test]
fn json_skeleton_preserves_values_and_layout() {
    for source in [
        r#"{
  "json": {},
  "markdown": {},
  "markup": {
    "indentWidth": 2
  },
  "excludes": [],
  "plugins": [
    "formatter-json",
    "formatter-markdown"
  ]
}"#,
        r#"{"values": ["café", "日本語", "line\nbreak", 42, -1.5, true, false, null], "nested": [[1, 2], {"enabled": true}]}"#,
        r#"[[], {}, ["entry"], {"items": [1, 2]}]"#,
    ] {
        let analysis = analyze(&Json, source);
        let skeleton = Json.render_skel(source, &analysis);
        let expected: serde_json::Value = serde_json::from_str(source).unwrap();
        let actual: serde_json::Value = serde_json::from_str(&skeleton).unwrap();

        assert_eq!(actual, expected, "source: {source}");
        assert_eq!(skeleton, source);
    }
}

#[test]
fn toml_skeleton_preserves_values_comments_and_layout() {
    for source in [
        r#"[dependency-groups]
dev = [
    "maturin>=1.16.0",
    "ruff>=0.14.0",
]

[tool.uv.workspace]
members = ["binding_python"]

[tool.pyrefly]
project-includes = [
  "**/*.py*",
  "**/*.ipynb",
]"#,
        r#"# Configuration
name = "café 日本語"
empty = []
nested = [[1, 2], []]
flags = [true, false]
values = [1.5, -2.0]
dates = [2026-01-02, 2026-01-02T03:04:05Z, 2026-01-02T03:04:05, 03:04:05]
items = [
    "first", # Keep this comment.
    "second",
]
settings = { enabled = true, names = ["one", "two"] }
message = """
Multiple lines
remain intact.
"""
literal = '''
Another multiline
value.
'''"#,
        r#"[[packages]]
name = "first"
features = ["default"]

[[packages]]
name = "second"
features = []"#,
    ] {
        let analysis = analyze(&Toml, source);
        let skeleton = Toml.render_skel(source, &analysis);
        let expected: toml::Value = toml::from_str(source).unwrap();
        let actual: toml::Value = toml::from_str(&skeleton).unwrap();

        assert_eq!(actual, expected, "source: {source}");
        assert_eq!(skeleton, source);
    }
}

#[test]
fn json_signatures_omit_scalar_values_and_array_entries() {
    let source = r#"{"plugins": ["formatter-a", "formatter-b"], "enabled": true}"#;
    let analysis = analyze(&Json, source);
    let signatures = Json.render_sigs(source, &analysis);

    assert!(signatures.contains("\"plugins\": ["));
    assert!(signatures.contains(']'));
    assert!(signatures.contains("\"enabled\":"));
    assert!(!signatures.contains("formatter-a"));
    assert!(!signatures.contains("formatter-b"));
    assert!(!signatures.contains("true"));
}

#[test]
fn toml_signatures_omit_scalar_values_array_entries_and_comments() {
    let source = "# Configuration\n[workspace]\nmembers = [\"binding_python\"]\nenabled = true\n";
    let analysis = analyze(&Toml, source);
    let signatures = Toml.render_sigs(source, &analysis);

    assert!(signatures.contains("[workspace]"));
    assert!(signatures.contains("members = ["));
    assert!(signatures.contains(']'));
    assert!(signatures.contains("enabled ="));
    assert!(!signatures.contains("binding_python"));
    assert!(!signatures.contains("true"));
    assert!(!signatures.contains("Configuration"));
}

#[test]
fn rust_outlines_preserve_indentation_without_retaining_bodies() {
    let source = r#"use std::fmt;

/// An item.
#[derive(Debug)]
pub struct Item {
    pub name: String,
}

impl Item {
    /// Creates an item.
    pub fn new(name: String) -> Self {
        Self { name }
    }
}
"#;
    let language = Rust::default();
    let analysis = analyze(&language, source);

    assert_eq!(
        language.render_sigs(source, &analysis),
        "use std::fmt;\npub struct Item\n    pub name: String\nimpl Item\n    pub fn new(name: String) -> Self"
    );
    assert_eq!(
        language.render_skel(source, &analysis),
        "use std::fmt;\n/// An item.\n#[derive(Debug)]\npub struct Item\n    pub name: String\nimpl Item\n    /// Creates an item.\n    pub fn new(name: String) -> Self"
    );
}
