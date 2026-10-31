use std::collections::{BTreeSet, HashMap, HashSet};
use std::ops::Range;
use std::sync::LazyLock;

use globset::GlobBuilder;
use la_arena::ArenaMap;
use regex::Regex;

use super::Graph;
use crate::Config;
use crate::index::{FileId, Index};
use crate::repo::Repository;

const FIELD_WEIGHTS: [f64; 4] = [5.0, 4.0, 2.5, 1.0];
const BM25_K1: f64 = 1.2;
const BM25_B: f64 = 0.75;
const ALPHA: f64 = 0.85;

static WORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\p{L}\p{N}_]{2,}").unwrap());
static ACRONYM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"([A-Z]+)([A-Z][a-z])").unwrap());
static CAMEL: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"([a-z0-9])([A-Z])").unwrap());

/// Ranks files with personalized PageRank and field-weighted lexical relevance.
#[derive(Debug)]
pub struct GraphScorer;

impl GraphScorer {
    /// Returns normalized file scores biased toward the configured focus.
    ///
    /// Combines field-weighted BM25 relevance and focused paths with dependency
    /// ranking. Empty indexes produce an empty score map.
    ///
    /// # Panics
    ///
    /// Panics if focus-file patterns are configured and an indexed path has no
    /// filename, or if a dependency of an indexed file is outside the index.
    pub fn score(
        index: &Index,
        repository: &Repository,
        graph: &Graph,
        config: &Config,
    ) -> ArenaMap<FileId, f64> {
        if index.files.is_empty() {
            return ArenaMap::new();
        }

        let terms: Vec<_> = tokenize(config.focus_query.as_deref().unwrap_or(""))
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect();
        let lexical = Self::bm25_scores(index, repository, &terms);
        let patterns: Vec<_> = config
            .focus_files
            .iter()
            .filter_map(|pattern| {
                let pattern = pattern.trim().replace('\\', "/");
                let pattern = pattern
                    .trim_start_matches("./")
                    .trim_start_matches('/')
                    .to_owned();

                if pattern.is_empty() {
                    return None;
                }

                // fnmatch treats repeated stars as one wildcard and braces as literals.
                let mut glob = String::new();

                for character in pattern.chars() {
                    if character == '*' && glob.ends_with('*') {
                        continue;
                    }
                    if matches!(character, '{' | '}') {
                        glob.push('\\');
                    }
                    glob.push(character);
                }

                let matcher = GlobBuilder::new(&glob)
                    .backslash_escape(true)
                    .literal_separator(false)
                    .allow_unclosed_class(true)
                    .build()
                    .ok()
                    .map(|glob| glob.compile_matcher());
                Some((pattern, matcher))
            })
            .collect();
        let mut has_focus = false;
        let mut preferences = ArenaMap::new();
        let mut degrees = ArenaMap::new();

        for (file, entry) in index.files.iter() {
            let focused = if patterns.is_empty() {
                false
            } else {
                let path = entry
                    .path
                    .to_string_lossy()
                    .replace(std::path::MAIN_SEPARATOR, "/");
                let filename = entry.path.file_name().unwrap().to_string_lossy();
                patterns.iter().any(|(pattern, matcher)| {
                    path == *pattern
                        || filename == pattern.as_str()
                        || path
                            .strip_prefix(pattern.trim_end_matches('/'))
                            .is_some_and(|suffix| suffix.starts_with('/'))
                        || matcher.as_ref().is_some_and(|matcher| {
                            matcher.is_match(&path) || matcher.is_match(filename.as_ref())
                        })
                })
            };
            has_focus |= focused;
            preferences.insert(file, 1.0 + f64::from(focused) + 3.5 * lexical[file]);
            degrees.insert(file, graph.neighbors(file).count());
        }

        if !terms.is_empty() || has_focus {
            Self::diffuse_preferences(graph, &degrees, &mut preferences);
        }

        let total: f64 = preferences.values().sum();

        for (_, preference) in preferences.iter_mut() {
            *preference /= total;
        }

        Self::pagerank(index, graph, &degrees, preferences)
    }

    fn bm25_scores(
        index: &Index,
        repository: &Repository,
        terms: &[String],
    ) -> ArenaMap<FileId, f64> {
        let mut scores: ArenaMap<_, _> = index.files.iter().map(|(file, _)| (file, 0.0)).collect();

        if terms.is_empty() {
            return scores;
        }

        let lookup: HashMap<_, _> = terms
            .iter()
            .enumerate()
            .map(|(index, term)| (term.as_str(), index))
            .collect();
        let mut documents = ArenaMap::new();
        let mut document_frequency = vec![0; terms.len()];
        let mut totals = [0; 4];

        for (file, entry) in index.files.iter() {
            let mut document = Document::default();
            let path = entry
                .path
                .to_string_lossy()
                .replace(std::path::MAIN_SEPARATOR, "/");
            document.count(0, &path, &lookup);

            if let Some(source) = repository.sources.get(file) {
                if let Some(analysis) = &source.analysis {
                    document.count_ranges(1, &source.bytes, &analysis.sigs, &lookup);
                    document.count_ranges(2, &source.bytes, &analysis.docstrings, &lookup);
                }

                document.count(3, std::str::from_utf8(&source.bytes).unwrap_or(""), &lookup);
            }

            for &term in document.frequencies.keys() {
                document_frequency[term] += 1;
            }

            for (total, length) in totals.iter_mut().zip(document.lengths) {
                *total += length;
            }

            documents.insert(file, document);
        }

        let count = index.files.len() as f64;
        let averages = totals.map(|total| total as f64 / count);
        let inverse_document_frequency: Vec<_> = document_frequency
            .into_iter()
            .map(|frequency| {
                let frequency = frequency as f64;
                ((count - frequency + 0.5) / (frequency + 0.5)).ln_1p()
            })
            .collect();

        for (file, document) in documents.iter() {
            for (term, &idf) in inverse_document_frequency.iter().enumerate() {
                let Some(frequencies) = document.frequencies.get(&term) else {
                    continue;
                };
                let mut normalized_tf = 0.0;

                for field in 0..4 {
                    if frequencies[field] != 0 {
                        let normalization = 1.0 - BM25_B
                            + BM25_B * document.lengths[field] as f64 / averages[field];
                        normalized_tf +=
                            FIELD_WEIGHTS[field] * frequencies[field] as f64 / normalization;
                    }
                }

                scores[file] += idf * normalized_tf * (BM25_K1 + 1.0) / (normalized_tf + BM25_K1);
            }
        }

        scores
    }

    fn diffuse_preferences(
        graph: &Graph,
        degrees: &ArenaMap<FileId, usize>,
        preferences: &mut ArenaMap<FileId, f64>,
    ) {
        let mut values: Vec<_> = preferences.values().copied().collect();
        let middle = values.len() / 2;
        let (_, &mut median, _) = values.select_nth_unstable_by(middle, f64::total_cmp);
        let base = preferences.clone();

        for (file, &preference) in base.iter() {
            if preference > 1.5 * median && degrees[file] != 0 {
                let share = 0.3 * (preference - median) / degrees[file] as f64;

                for neighbor in graph.neighbors(file) {
                    preferences[neighbor] += share;
                }
            }
        }
    }

    fn pagerank(
        index: &Index,
        graph: &Graph,
        degrees: &ArenaMap<FileId, usize>,
        preferences: ArenaMap<FileId, f64>,
    ) -> ArenaMap<FileId, f64> {
        let mut ranks = preferences.clone();
        let mut next = ArenaMap::new();
        let tolerance = index.files.len() as f64 * 1e-6;

        for _ in 0..200 {
            let dangling: f64 = ranks
                .iter()
                .filter(|(file, _)| degrees[*file] == 0)
                .map(|(_, rank)| rank)
                .sum();
            let base = 1.0 - ALPHA + ALPHA * dangling;

            for (file, &preference) in preferences.iter() {
                next.insert(file, base * preference);
            }

            for (file, &rank) in ranks.iter() {
                if degrees[file] != 0 {
                    let share = ALPHA * rank / degrees[file] as f64;

                    for neighbor in graph.neighbors(file) {
                        next[neighbor] += share;
                    }
                }
            }

            let error: f64 = ranks
                .iter()
                .map(|(file, rank)| (next[file] - rank).abs())
                .sum();
            std::mem::swap(&mut ranks, &mut next);

            if error < tolerance {
                break;
            }
        }

        let total: f64 = ranks.values().sum();

        for (_, rank) in ranks.iter_mut() {
            *rank /= total;
        }

        ranks
    }
}

#[derive(Default)]
struct Document {
    lengths: [usize; 4],
    frequencies: HashMap<usize, [usize; 4]>,
}

impl Document {
    fn count(&mut self, field: usize, text: &str, terms: &HashMap<&str, usize>) {
        for token in tokenize(text) {
            self.lengths[field] += 1;

            if let Some(&term) = terms.get(token.as_str()) {
                self.frequencies.entry(term).or_default()[field] += 1;
            }
        }
    }

    fn count_ranges(
        &mut self,
        field: usize,
        source: &[u8],
        ranges: &[Range<usize>],
        terms: &HashMap<&str, usize>,
    ) {
        // Queries can capture nested declarations; count overlapping bytes only once.
        let mut merged = 0..0;

        for range in ranges {
            if range.start <= merged.end {
                merged.end = merged.end.max(range.end);
            } else {
                if let Some(text) = source
                    .get(merged)
                    .and_then(|bytes| std::str::from_utf8(bytes).ok())
                {
                    self.count(field, text, terms);
                }
                merged = range.clone();
            }
        }

        if let Some(text) = source
            .get(merged)
            .and_then(|bytes| std::str::from_utf8(bytes).ok())
        {
            self.count(field, text, terms);
        }
    }
}

fn tokenize(text: &str) -> impl Iterator<Item = String> + '_ {
    WORD.find_iter(text).flat_map(|matched| {
        let word = matched.as_str();
        let split = ACRONYM.replace_all(word, "${1}_${2}");
        let split = CAMEL.replace_all(&split, "${1}_${2}").to_lowercase();
        let mut tokens = HashSet::from([word.to_lowercase()]);
        tokens.extend(
            split
                .split('_')
                .filter(|part| part.chars().count() >= 2)
                .map(str::to_owned),
        );
        tokens.into_iter()
    })
}
