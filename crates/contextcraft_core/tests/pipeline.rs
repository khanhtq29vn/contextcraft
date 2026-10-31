mod common;

use std::num::NonZeroUsize;

use contextcraft_core::error::Error;
use contextcraft_core::tokens::TokenCounter;
use contextcraft_core::{Config, ContextCraft, OutputFormat, TokenizerEncoding};

#[test]
fn artifacts_respect_budgets_and_match_between_execution_modes() {
    let root = common::fixture(&[
        (
            "Cargo.toml",
            "[package]\nname = 'fixture'\nversion = '0.1.0'\n",
        ),
        (
            "src/lib.rs",
            "pub mod auth;\npub fn ready() -> bool { true }\n",
        ),
        (
            "src/auth.rs",
            "/// Authenticate a user.\npub fn authenticate(name: &str) -> bool { !name.is_empty() }\n",
        ),
        ("settings.json", "{\"roles\": [\"admin\", \"reader\"]}"),
        ("notes.txt", "Authentication uses café credentials.\n"),
    ]);

    for format in [
        OutputFormat::Markdown,
        OutputFormat::Xml,
        OutputFormat::Json,
    ] {
        for encoding in [TokenizerEncoding::Cl100kBase, TokenizerEncoding::O200kBase] {
            for budget in [64, 256, 2_000] {
                let mut config = Config {
                    enable_parallel: false,
                    output_format: format,
                    tokenizer_encoding: encoding,
                    budget_tokens: NonZeroUsize::new(budget).unwrap(),
                    focus_query: Some("authenticate user".into()),
                    focus_files: vec!["src/auth.rs".into()],
                    ..Config::default()
                };
                let serial = ContextCraft::new(config.clone()).run(root.path()).unwrap();
                config.enable_parallel = true;
                let parallel = ContextCraft::new(config).run(root.path()).unwrap();
                let counter = TokenCounter::new(encoding, false).unwrap();

                assert_eq!(serial.artifact, parallel.artifact);
                assert_eq!(
                    counter.count(&serial.artifact.content).unwrap(),
                    serial.artifact.tokens
                );
                assert!(serial.artifact.tokens <= budget);
                assert!(!serial.artifact.token_counts_estimated);
                assert_eq!(
                    serial.artifact.selected_tiers.iter().count(),
                    serial.index.files.len()
                );
                assert!(
                    serial
                        .scores
                        .values()
                        .all(|score| score.is_finite() && *score >= 0.0)
                );
                assert!((serial.scores.values().sum::<f64>() - 1.0).abs() < 1e-12);

                for (file, source) in serial.repository.sources.iter() {
                    assert_eq!(source.bytes, parallel.repository.sources[file].bytes);
                    assert_eq!(source.analysis, parallel.repository.sources[file].analysis);
                }

                match format {
                    OutputFormat::Json => {
                        let value: serde_json::Value =
                            serde_json::from_str(&serial.artifact.content).unwrap();
                        assert!(value["files"].is_array());
                    }
                    OutputFormat::Xml => {
                        let document =
                            roxmltree::Document::parse(&serial.artifact.content).unwrap();
                        assert_eq!(
                            document.root_element().tag_name().name(),
                            "repository_context"
                        );
                    }
                    OutputFormat::Markdown => assert!(
                        serial
                            .artifact
                            .content
                            .starts_with("# Repository context\n")
                    ),
                }
            }
        }
    }
}

#[test]
fn empty_repositories_produce_valid_artifacts_or_a_budget_error() {
    let root = common::fixture(&[]);

    for format in [
        OutputFormat::Markdown,
        OutputFormat::Xml,
        OutputFormat::Json,
    ] {
        let mut config = Config {
            output_format: format,
            ..Config::default()
        };
        let analysis = ContextCraft::new(config.clone()).run(root.path()).unwrap();
        assert!(analysis.index.files.is_empty());
        assert_eq!(analysis.scores.iter().count(), 0);
        assert_eq!(analysis.artifact.selected_tiers.iter().count(), 0);

        config.budget_tokens = NonZeroUsize::new(1).unwrap();
        assert!(matches!(
            ContextCraft::new(config).run(root.path()),
            Err(Error::BudgetTooSmall { budget: 1, minimum }) if minimum > 1
        ));
    }
}

#[test]
fn repeated_runs_produce_identical_artifacts() {
    let root = common::fixture(&[
        ("main.py", "from helper import ready\nprint(ready())\n"),
        ("helper.py", "def ready():\n    return True\n"),
    ]);
    let pipeline = ContextCraft::default();
    let expected = pipeline.run(root.path()).unwrap().artifact;

    for _ in 0..4 {
        assert_eq!(pipeline.run(root.path()).unwrap().artifact, expected);
    }
}
