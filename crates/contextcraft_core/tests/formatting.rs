mod common;

use std::num::NonZeroUsize;

use contextcraft_core::error::Error;
use contextcraft_core::formatter::ArtifactFormatter;
use contextcraft_core::optimizer::BudgetAllocator;
use contextcraft_core::tiers::FidelityLevel;
use contextcraft_core::tokens::TokenCounter;
use contextcraft_core::{Config, ContextCraft, OutputFormat, TokenizerEncoding};

#[test]
fn json_file_blocks_round_trip_paths_and_source_text() {
    let path = "dir/\"quoted\" & <café>\nfile.json";
    let content = "quotes: \" \\ tabs:\t lines:\r\n日本語 <&>\u{0}";
    let block =
        ArtifactFormatter::render_file(path, content, FidelityLevel::Full, OutputFormat::Json);
    let value: serde_json::Value = serde_json::from_str(&block).unwrap();

    assert_eq!(value["path"], path);
    assert_eq!(value["content"], content);
    assert_eq!(value["tier"], "FULL");
}

#[test]
fn xml_file_blocks_escape_attributes_and_text() {
    let path = "dir/\"quoted\" & 'name'\t\n\r.xml";
    let content = "<&> café\r\n\u{0}\u{b}\u{fffe}";
    let block =
        ArtifactFormatter::render_file(path, content, FidelityLevel::Skel, OutputFormat::Xml);
    let document = roxmltree::Document::parse(&block).unwrap();
    let file = document.root_element();

    assert_eq!(file.attribute("path"), Some(path));
    assert_eq!(file.attribute("tier"), Some("SKEL"));
    assert_eq!(file.text(), Some("<&> café\r\n\u{fffd}\u{fffd}\u{fffd}"));

    let empty = ArtifactFormatter::render_file(path, "", FidelityLevel::Full, OutputFormat::Xml);
    assert!(empty.ends_with(" />"));
    assert!(roxmltree::Document::parse(&empty).is_ok());
}

#[test]
fn markdown_fences_are_longer_than_every_source_backtick_run() {
    for content in ["", "plain", "```\ncode\n```", "embedded ````` fence"] {
        let block = ArtifactFormatter::render_file(
            "src/__init__.py",
            content,
            FidelityLevel::Full,
            OutputFormat::Markdown,
        );
        let fence = block.lines().nth(2).unwrap();
        let longest = content
            .split(|character| character != '`')
            .map(str::len)
            .max()
            .unwrap();

        assert!(fence.len() >= 3);
        assert!(fence.len() > longest);
        assert!(block.contains("\"src/__init__.py\""));
        assert!(block.ends_with(&format!("\n{fence}\n\n")));
        assert!(block.contains(content));
    }
}

#[test]
fn path_only_tiers_have_no_file_block_or_framed_cost() {
    let counter = TokenCounter::new(TokenizerEncoding::Cl100kBase, false).unwrap();

    for format in [
        OutputFormat::Markdown,
        OutputFormat::Xml,
        OutputFormat::Json,
    ] {
        assert_eq!(
            ArtifactFormatter::render_file("file", "content", FidelityLevel::Tree, format),
            ""
        );
        assert_eq!(
            ArtifactFormatter::file_cost("file", "content", FidelityLevel::Tree, &counter, format)
                .unwrap(),
            0
        );
    }
}

#[test]
fn formatter_downgrades_oversized_full_selections() {
    let source: String = (0..200)
        .map(|i| format!("item_{i} has distinct content\n"))
        .collect();
    let root = common::fixture(&[("source.txt", &source)]);

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
        let mut selection =
            BudgetAllocator::allocate(&analysis.index, &analysis.tiers, &analysis.scores, &config)
                .unwrap();
        for (_, level) in selection.tiers.iter_mut() {
            *level = FidelityLevel::Full;
        }
        config.budget_tokens = NonZeroUsize::new(64).unwrap();
        let artifact = ArtifactFormatter::format(
            &analysis.index,
            &analysis.tiers,
            &analysis.scores,
            &selection,
            &config,
        )
        .unwrap();
        let counter = TokenCounter::new(config.tokenizer_encoding, false).unwrap();

        assert!(artifact.tokens <= 64);
        assert_eq!(artifact.tokens, counter.count(&artifact.content).unwrap());
        assert!(
            artifact
                .selected_tiers
                .values()
                .all(|level| *level < FidelityLevel::Full)
        );
    }
}

#[test]
fn inconsistent_pipeline_inputs_return_errors() {
    let root = common::fixture(&[("source.txt", "content")]);
    let config = Config::default();
    let analysis = ContextCraft::new(config.clone()).run(root.path()).unwrap();
    let selection =
        BudgetAllocator::allocate(&analysis.index, &analysis.tiers, &analysis.scores, &config)
            .unwrap();
    let file = analysis.index.files.iter().next().unwrap().0;

    for invalid in [f64::NAN, f64::INFINITY, -1.0] {
        let mut scores = analysis.scores.clone();
        scores.insert(file, invalid);
        assert!(matches!(
            BudgetAllocator::allocate(&analysis.index, &analysis.tiers, &scores, &config),
            Err(Error::InvalidPipeline(_))
        ));
    }

    let mut incomplete = selection.clone();
    incomplete.tiers = Default::default();
    assert!(matches!(
        ArtifactFormatter::render(&analysis.index, &analysis.tiers, &incomplete, &[], &config),
        Err(Error::InvalidPipeline(_))
    ));
    assert!(matches!(
        ArtifactFormatter::render(
            &analysis.index,
            &analysis.tiers,
            &selection,
            &[file, file],
            &config
        ),
        Err(Error::InvalidPipeline(_))
    ));

    let different_format = Config {
        output_format: OutputFormat::Json,
        ..config.clone()
    };
    assert!(matches!(
        BudgetAllocator::allocate(
            &analysis.index,
            &analysis.tiers,
            &analysis.scores,
            &different_format
        ),
        Err(Error::InvalidPipeline(_))
    ));
    let different_encoding = Config {
        tokenizer_encoding: TokenizerEncoding::O200kBase,
        ..config
    };
    assert!(matches!(
        BudgetAllocator::allocate(
            &analysis.index,
            &analysis.tiers,
            &analysis.scores,
            &different_encoding
        ),
        Err(Error::InvalidPipeline(_))
    ));
}

#[test]
fn missing_tiers_and_scores_are_rejected() {
    let root = common::fixture(&[("source.txt", "content")]);
    let config = Config::default();
    let mut analysis = ContextCraft::new(config.clone()).run(root.path()).unwrap();
    let selection =
        BudgetAllocator::allocate(&analysis.index, &analysis.tiers, &analysis.scores, &config)
            .unwrap();
    let scores = la_arena::ArenaMap::new();
    assert!(matches!(
        BudgetAllocator::allocate(&analysis.index, &analysis.tiers, &scores, &config),
        Err(Error::InvalidPipeline(_))
    ));

    let file = analysis.index.files.iter().next().unwrap().0;
    let selected = selection.tiers[file];
    analysis.tiers.files[file].levels[selected as usize] = None;
    assert!(matches!(
        ArtifactFormatter::format(
            &analysis.index,
            &analysis.tiers,
            &analysis.scores,
            &selection,
            &config
        ),
        Err(Error::InvalidPipeline(_))
    ));
}
