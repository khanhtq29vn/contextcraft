mod common;

use contextcraft_core::Config;
use contextcraft_core::graph::{Graph, GraphScorer};
use contextcraft_core::index::Indexer;
use contextcraft_core::repo::RepositoryReader;

#[test]
fn focus_directories_respect_path_boundaries() {
    let root = common::fixture(&[
        ("src/a.txt", "same content"),
        ("src-extra/a.txt", "same content"),
    ]);
    let config = Config {
        focus_files: vec!["src".into()],
        ..Config::default()
    };
    let index = Indexer::new().index(root.path(), &config).unwrap();
    let repository = RepositoryReader::new().read(&index, &config).unwrap();
    let graph = Graph::new(&index, &repository);
    let scores = GraphScorer::score(&index, &repository, &graph, &config);
    let find = |path: &str| {
        index
            .files
            .iter()
            .find(|(_, file)| file.path == std::path::Path::new(path))
            .unwrap()
            .0
    };

    assert!(scores[find("src/a.txt")] > scores[find("src-extra/a.txt")]);
}

#[test]
fn lexical_focus_matches_identifier_parts_and_unicode_terms() {
    let root = common::fixture(&[
        ("match.txt", "HTTPAuthenticator user_name café 日本語"),
        ("other.txt", "unrelated renderer configuration"),
    ]);
    let index = Indexer::new()
        .index(root.path(), &Config::default())
        .unwrap();
    let repository = RepositoryReader::new()
        .read(&index, &Config::default())
        .unwrap();
    let graph = Graph::new(&index, &repository);
    let matching = index
        .files
        .iter()
        .find(|(_, file)| file.path == std::path::Path::new("match.txt"))
        .unwrap()
        .0;
    let other = index
        .files
        .iter()
        .find(|(_, file)| file.path == std::path::Path::new("other.txt"))
        .unwrap()
        .0;

    for query in ["authenticator", "name", "café", "日本語"] {
        let config = Config {
            focus_query: Some(query.into()),
            ..Config::default()
        };
        let scores = GraphScorer::score(&index, &repository, &graph, &config);
        assert!(scores[matching] > scores[other], "query: {query}");
    }
}

#[test]
fn dangling_nodes_and_cycles_produce_finite_normalized_scores() {
    let root = common::fixture(&[("a.txt", "a"), ("b.txt", "b"), ("c.txt", "c")]);
    let config = Config::default();
    let index = Indexer::new().index(root.path(), &config).unwrap();
    let repository = RepositoryReader::new().read(&index, &config).unwrap();
    let files: Vec<_> = index.files.iter().map(|(file, _)| file).collect();
    let mut graph = Graph::new(&index, &repository);
    graph.dependencies.add_edge(files[0], files[1], ());
    graph.dependencies.add_edge(files[1], files[0], ());
    let scores = GraphScorer::score(&index, &repository, &graph, &config);

    assert!(
        scores
            .values()
            .all(|score| score.is_finite() && *score >= 0.0)
    );
    assert!((scores.values().sum::<f64>() - 1.0).abs() < 1e-12);
    assert!((scores[files[0]] - scores[files[1]]).abs() < 1e-12);
    assert!(scores[files[0]] > scores[files[2]]);
}

#[test]
fn focus_globs_and_normalized_paths_identify_the_same_file() {
    let root = common::fixture(&[("src/target.txt", "content"), ("other.txt", "content")]);
    let config = Config::default();
    let index = Indexer::new().index(root.path(), &config).unwrap();
    let repository = RepositoryReader::new().read(&index, &config).unwrap();
    let graph = Graph::new(&index, &repository);
    let mut expected = None;

    for pattern in [
        "src/target.txt",
        "./src/target.txt",
        "src\\target.txt",
        "target.txt",
        "src/*.txt",
    ] {
        let config = Config {
            focus_files: vec![pattern.into()],
            ..Config::default()
        };
        let scores = GraphScorer::score(&index, &repository, &graph, &config);
        if let Some(expected) = &expected {
            assert_eq!(&scores, expected, "pattern: {pattern}");
        } else {
            expected = Some(scores);
        }
    }
}
