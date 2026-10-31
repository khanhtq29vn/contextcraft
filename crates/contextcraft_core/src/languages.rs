//! Language grammars, outline capture queries, and local dependency resolution.

use std::collections::BTreeMap;
use std::fmt::Debug;
use std::ops::Range;
use std::path::Path;

use tree_sitter as ts;
use ts::StreamingIterator;

use crate::Config;
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::package::{Package, PackageResolution};
use crate::repo::{Analysis, Repository};

mod component;
mod local;

pub mod bash;
pub mod c;
pub mod cmake;
pub mod cpp;
pub mod csharp;
pub mod css;
pub mod dockerfile;
pub mod elixir;
pub mod go;
pub mod graphql;
pub mod hcl;
pub mod html;
pub mod javascript;
pub mod json;
pub mod just;
pub mod kotlin;
pub mod lua;
pub mod make;
pub mod markdown;
pub mod protobuf;
pub mod python;
pub mod rst;
pub mod ruby;
pub mod rust;
pub mod scala;
pub mod scss;
pub mod sql;
pub mod svelte;
pub mod swift;
pub mod toml;
pub mod typescript;
pub mod vue;
pub mod yaml;
pub mod zig;

/// Per-repository state shared by parallel file analysis and dependency resolution.
///
/// [`RepositoryReader`](crate::repo::RepositoryReader) may call
/// [`extract_dependencies`](Self::extract_dependencies) concurrently for different
/// files. Implementations must synchronize mutations; extract file-local data
/// before acquiring shared-state locks to avoid serializing syntax traversal.
pub trait LanguageAnalysis: Debug + Send + Sync {
    /// Records dependencies captured from one file. The default does nothing.
    ///
    /// Nodes and byte offsets refer to `source`, after optional secret redaction.
    fn extract_dependencies(&self, _file: FileId, _nodes: &[ts::Node<'_>], _source: &[u8]) {}

    /// Returns directed `(importer, dependency)` file edges within the index.
    fn resolve_dependencies(&self, index: &Index, repository: &Repository)
    -> Vec<(FileId, FileId)>;
}

impl LanguageAnalysis for () {
    fn resolve_dependencies(
        &self,
        _index: &Index,
        _repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        Vec::new()
    }
}

/// Language-specific parsing, outline rendering, and package resolution.
pub trait Language: Debug + Send + Sync {
    /// Returns the stable language ID used by the index and analysis maps.
    fn id(&self) -> &'static str;

    /// Dialects with different grammars can share project ownership.
    fn package_language(&self) -> &'static str {
        self.id()
    }

    /// Returns the Tree-sitter grammar used to parse source.
    fn grammar(&self) -> ts::Language;

    /// Returns the Tree-sitter query for outline and dependency captures.
    fn source_query(&self) -> &'static str;

    /// Compiles the outline and dependency query for this grammar.
    ///
    /// # Errors
    ///
    /// Returns an error if the query is invalid for the grammar.
    fn query(&self) -> Result<ts::Query, Error> {
        Ok(ts::Query::new(&self.grammar(), self.source_query())?)
    }

    /// Creates repository-local dependency state shared by parallel file analysis.
    fn create_analysis(&self) -> Box<dyn LanguageAnalysis>;

    /// Allows outlines from recovered syntax trees. Defaults to `true`.
    fn allow_partial_analysis(&self) -> bool {
        true
    }

    /// Adds ranges for embedded languages or narrowly supported grammar extensions.
    fn supplement_analysis(
        &self,
        _file: FileId,
        _root: ts::Node<'_>,
        _source: &[u8],
        _analysis: &mut Analysis,
    ) {
    }

    /// Captures outline ranges and records dependencies in repository-local state.
    ///
    /// The query must be compiled for this language's grammar. Returned ranges
    /// are sorted and deduplicated byte offsets into `source`; overlapping ranges
    /// are retained. The parser can be reused for subsequent files.
    ///
    /// # Errors
    ///
    /// Returns an error if the parser cannot use the grammar or produce a tree.
    fn analyze(
        &self,
        file: FileId,
        parser: &mut ts::Parser,
        query: &ts::Query,
        source: &[u8],
        state: &dyn LanguageAnalysis,
    ) -> Result<Analysis, Error> {
        parser.set_language(&self.grammar())?;
        let tree = parser.parse(source, None).ok_or(Error::Parse)?;
        if !self.allow_partial_analysis() && tree.root_node().has_error() {
            return Ok(Analysis::default());
        }

        let mut cursor = ts::QueryCursor::new();
        let mut matches = cursor.matches(query, tree.root_node(), source);
        let mut analysis = Analysis::default();
        let mut dependencies = Vec::new();

        while let Some(matched) = matches.next() {
            let mut header_start = None;
            let mut header_end = None;
            let mut inclusive_end = false;

            for capture in matched.captures() {
                let node = capture.node;

                match query.capture_names()[capture.index as usize] {
                    "docstring" => analysis.docstrings.push(node.byte_range()),
                    "import.statement" => analysis.imports.push(node.byte_range()),
                    "decorator" | "skel.doc" => analysis.skel.push(node.byte_range()),
                    "header.start" => header_start = Some(node),
                    "header.end" => header_end = Some(node),
                    "header.end.inclusive" => {
                        header_end = Some(node);
                        inclusive_end = true;
                    }
                    "dependency" => dependencies.push(node),
                    _ => {}
                }
            }

            if let (Some(start), Some(end)) = (header_start, header_end) {
                let end_byte = if start == end || inclusive_end {
                    end.end_byte()
                } else {
                    end.start_byte()
                };

                let range = start.start_byte()..end_byte;
                analysis.sigs.push(range.clone());
                analysis.skel.push(range);
            }
        }

        self.supplement_analysis(file, tree.root_node(), source, &mut analysis);

        for ranges in [
            &mut analysis.docstrings,
            &mut analysis.imports,
            &mut analysis.sigs,
            &mut analysis.skel,
        ] {
            ranges.sort_unstable_by_key(|range| (range.start, range.end));
            ranges.dedup();
        }

        state.extract_dependencies(file, &dependencies, source);

        Ok(analysis)
    }

    /// Render a declaration outline, not necessarily executable source.
    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_spans(source, analysis.imports.iter().chain(&analysis.sigs), true)
    }

    /// Render a documented outline without reparsing the source.
    fn render_skel(&self, source: &str, analysis: &Analysis) -> String {
        render_spans(
            source,
            analysis
                .imports
                .iter()
                .chain(&analysis.sigs)
                .chain(&analysis.skel)
                .chain(&analysis.docstrings),
            true,
        )
    }

    /// Checks whether a matching marker is a real package boundary.
    ///
    /// The default accepts every marker.
    ///
    /// # Errors
    ///
    /// Returns an error if inspecting the candidate manifest fails.
    fn is_package_manifest(
        &self,
        _index: &Index,
        _path: &Path,
        _config: &Config,
    ) -> Result<bool, Error> {
        Ok(true)
    }

    /// Groups accepted package markers by their parent directory.
    ///
    /// # Errors
    ///
    /// Returns an error if inspecting a candidate manifest fails.
    fn discover_packages(&self, index: &Index, config: &Config) -> Result<Vec<Package>, Error> {
        let mut packages = BTreeMap::new();

        for (_, file) in index.files.iter() {
            if file
                .path
                .file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| self.package_markers().contains(&name))
                && self.is_package_manifest(index, &file.path, config)?
            {
                let root = file.path.parent().unwrap().to_path_buf();
                packages
                    .entry(root.clone())
                    .or_insert_with(|| Package {
                        root,
                        name: None,
                        language: Some(self.package_language()),
                        manifests: Vec::new(),
                        targets: Vec::new(),
                        dependencies: Vec::new(),
                    })
                    .manifests
                    .push(file.path.clone());
            }
        }

        Ok(packages.into_values().collect())
    }

    /// Resolves local packages after package IDs and file ownership are assigned.
    ///
    /// # Errors
    ///
    /// Returns an error if package metadata cannot be read or parsed.
    fn resolve_packages(
        &mut self,
        index: &Index,
        config: &Config,
    ) -> Result<PackageResolution, Error>;

    /// Resolves local file dependencies from the repository's language state.
    ///
    /// Returns an empty list when no analysis exists for this language.
    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        repository
            .analyses
            .get(self.id())
            .map(|analysis| analysis.resolve_dependencies(index, repository))
            .unwrap_or_default()
    }

    /// Uses `ignore::overrides` syntax: `!` prefixes exclusions.
    fn ignore_patterns(&self) -> &'static [&'static str];

    /// Returns filenames that may establish package boundaries.
    fn package_markers(&self) -> &'static [&'static str];

    /// Returns recognized package and tool metadata filenames.
    ///
    /// This metadata list does not itself control scanning exclusions.
    fn package_metadata_files(&self) -> &'static [&'static str];

    /// Recognizes conventional source filenames before extension-based detection.
    fn matches_filename(&self, _name: &str) -> bool {
        false
    }

    /// Returns recognized, case-sensitive source extensions, including the leading dot.
    fn file_extensions(&self) -> &'static [&'static str];
}

fn render_outline(source: &str, analysis: &Analysis, skeleton: bool) -> String {
    render_spans(
        source,
        analysis
            .imports
            .iter()
            .chain(&analysis.sigs)
            .chain(analysis.skel.iter().filter(|_| skeleton))
            .chain(analysis.docstrings.iter().filter(|_| skeleton)),
        false,
    )
}

fn render_spans<'a>(
    source: &str,
    spans: impl Iterator<Item = &'a Range<usize>>,
    preserve_columns: bool,
) -> String {
    let mut spans: Vec<_> = spans
        .filter(|span| span.start < span.end && source.get((*span).clone()).is_some())
        .cloned()
        .collect();
    spans.sort_unstable_by_key(|span| (span.start, span.end));
    let mut spans = spans.into_iter().peekable();
    let mut output = String::new();
    let mut previous_end = 0;

    while let Some(mut span) = spans.next() {
        while let Some(next) = spans.next_if(|next| next.start <= span.end) {
            span.end = span.end.max(next.end);
        }

        let text = source[span.clone()].trim_end();

        if text.is_empty() {
            continue;
        }

        if !output.is_empty() {
            let gap = &source[previous_end..span.start];

            // Data outlines retain separators and spacing between captured tokens.
            if !preserve_columns
                && gap
                    .chars()
                    .all(|character| character.is_whitespace() || character == ',')
            {
                output.push_str(gap);
                output.push_str(text);
                previous_end = span.start + text.len();
                continue;
            }

            output.push('\n');
        }

        let line_start = source.as_bytes()[..span.start]
            .iter()
            .rposition(|&byte| byte == b'\n')
            .map_or(0, |position| position + 1);
        let prefix = &source[line_start..span.start];

        if prefix
            .chars()
            .all(|character| matches!(character, ' ' | '\t'))
        {
            output.push_str(prefix);
        } else if preserve_columns {
            output.extend(std::iter::repeat_n(' ', span.start - line_start));
        }

        output.push_str(text);
        previous_end = span.start + text.len();
    }

    output
}

#[cfg(test)]
mod tests {
    use super::render_spans;

    #[test]
    fn data_spans_preserve_commas_spacing_and_indentation() {
        let source = "{\n  \"first\": 1,\n  \"second\": []\n}";
        let spans: Vec<_> = ["{", "\"first\": 1", "\"second\":", "[", "]", "}"]
            .into_iter()
            .map(|text| {
                let start = source.find(text).unwrap();
                start..start + text.len()
            })
            .collect();

        assert_eq!(render_spans(source, spans.iter(), false), source);
    }

    #[test]
    fn overlapping_duplicate_and_unordered_spans_are_merged() {
        let source = "first, second";
        let spans = [7..13, 0..5, 0..3, 0..5];

        assert_eq!(render_spans(source, spans.iter(), false), source);
    }

    #[test]
    fn omitted_values_are_not_restored_between_spans() {
        let source = "first = \"omitted\"\nsecond = true";
        let second = source.find("second").unwrap();
        let spans = [0..7, second..source.len()];

        assert_eq!(
            render_spans(source, spans.iter(), false),
            "first =\nsecond = true"
        );
    }
}
