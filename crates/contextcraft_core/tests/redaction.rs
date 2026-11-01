mod common;

use std::fs;
use std::num::NonZeroUsize;

use contextcraft_core::error::Error;
use contextcraft_core::index::Indexer;
use contextcraft_core::repo::RepositoryReader;
use contextcraft_core::{Config, ContextCraft};

#[test]
fn redaction_removes_secrets_before_analysis_and_preserves_offsets() {
    let key = "AKIAIOSFODNN7EXAMPLE";
    let label = "PRIVATE KEY";
    let private_key =
        format!("-----BEGIN {label}-----\r\nYWJjZGVmZ2hpamtsbW5vcA==\r\n-----END {label}-----");
    let text = format!("café\r\n{key}\r\n{private_key}\r\n");
    let python = format!("KEY = '{key}'\n\ndef authenticate():\n    return True\n");
    let root = common::fixture(&[("credentials.txt", &text), ("auth.py", &python)]);
    let analysis = ContextCraft::default().run(root.path()).unwrap();
    let mut changed = 0;

    for (file, source) in analysis.repository.sources.iter() {
        let original = fs::read(root.path().join(&analysis.index.files[file].path)).unwrap();
        assert_eq!(source.bytes.len(), original.len());
        assert!(std::str::from_utf8(&source.bytes).is_ok());

        for (&before, &after) in original.iter().zip(&source.bytes) {
            if matches!(before, b'\r' | b'\n') {
                assert_eq!(after, before);
            }
            changed += usize::from(before != after);
        }

        let redacted = std::str::from_utf8(&source.bytes).unwrap();
        assert!(!redacted.contains(key));
        assert!(!redacted.contains("YWJjZGVmZ2hpamtsbW5vcA=="));

        if let Some(captures) = &source.analysis {
            for range in &captures.sigs {
                assert!(redacted.get(range.clone()).is_some());
            }
            assert!(
                captures
                    .sigs
                    .iter()
                    .any(|range| redacted[range.clone()].contains("authenticate"))
            );
        }
    }

    assert!(changed >= key.len() * 2);
    for (_, file) in analysis.tiers.files.iter() {
        for tier in file.levels.iter().flatten() {
            assert!(!tier.content.contains(key));
            assert!(!tier.content.contains("YWJjZGVmZ2hpamtsbW5vcA=="));
        }
    }
    assert!(!analysis.artifact.content.contains(key));
    assert!(
        !analysis
            .artifact
            .content
            .contains("YWJjZGVmZ2hpamtsbW5vcA==")
    );
}

#[test]
fn redaction_can_be_disabled() {
    let text = "AWS_KEY=AKIAIOSFODNN7EXAMPLE\n";
    let root = common::fixture(&[("credentials.txt", text)]);
    let config = Config {
        redact_secrets: false,
        ..Config::default()
    };
    let analysis = ContextCraft::new(config).run(root.path()).unwrap();

    assert_eq!(
        analysis.repository.sources.values().next().unwrap().bytes,
        text.as_bytes()
    );
    assert!(analysis.artifact.content.contains(text));
}

#[test]
fn reading_skips_unreadable_sources_and_obeys_the_exact_size_limit() {
    let root = common::fixture(&[
        ("at-limit.txt", "12345678"),
        ("over-limit.txt", "123456789"),
        ("empty.txt", ""),
    ]);
    fs::write(root.path().join("binary.dat"), [0, 1, 2]).unwrap();
    fs::write(root.path().join("invalid.txt"), [0xff, 0xfe]).unwrap();
    let config = Config {
        max_file_size_bytes: NonZeroUsize::new(8).unwrap(),
        ..Config::default()
    };
    let analysis = ContextCraft::new(config).run(root.path()).unwrap();
    let loaded: Vec<_> = analysis
        .repository
        .sources
        .iter()
        .map(|(file, _)| analysis.index.files[file].path.to_str().unwrap())
        .collect();

    assert_eq!(loaded, ["at-limit.txt", "empty.txt"]);
    assert_eq!(analysis.index.files.len(), 5);
    for (file, entry) in analysis.index.files.iter() {
        if !loaded.contains(&entry.path.to_str().unwrap()) {
            assert_eq!(
                analysis.tiers.files[file].levels.iter().flatten().count(),
                1
            );
        }
    }
}

#[test]
fn files_removed_after_indexing_report_io_errors() {
    let root = common::fixture(&[("source.txt", "content")]);
    let config = Config::default();
    let index = Indexer::new().index(root.path(), &config).unwrap();
    fs::remove_file(root.path().join("source.txt")).unwrap();

    assert!(matches!(
        RepositoryReader::new().read(&index, &config),
        Err(Error::Io { .. })
    ));
}
