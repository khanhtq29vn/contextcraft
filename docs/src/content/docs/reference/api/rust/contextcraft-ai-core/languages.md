---
title: "contextcraft-ai-core::languages"
description: "Language grammars, outline capture queries, and local dependency resolution."
editUrl: false
sidebar:
  order: 12
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Language grammars, outline capture queries, and local dependency resolution.

## Traits

### <span id="trait.LanguageAnalysis"></span><code style="font-size: 0.85em">trait LanguageAnalysis</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Supertraits:** `Debug + Send + Sync`

Per-repository state shared by parallel file analysis and dependency resolution.

[`RepositoryReader`](../../../rust/contextcraft-ai-core/repo/#struct.RepositoryReader) may call
`extract_dependencies` concurrently for different
files. Implementations must synchronize mutations; extract file-local data
before acquiring shared-state locks to avoid serializing syntax traversal.

#### Methods

##### <span id="LanguageAnalysis.extract_dependencies"></span><code>extract_​dependencies</code>

```rust
fn extract_dependencies(
    &self,
    _file: FileId,
    _nodes: &[ts::Node<'_>],
    _source: &[u8],
)
```

Records dependencies captured from one file. The default does nothing.

Nodes and byte offsets refer to `source`, after optional secret redaction.

<details>
<summary>Source</summary>

```rust
    fn extract_dependencies(&self, _file: FileId, _nodes: &[ts::Node<'_>], _source: &[u8]) {}
```

</details>

##### <span id="LanguageAnalysis.resolve_dependencies"></span><code>resolve_​dependencies</code>

```rust
fn resolve_dependencies(
    &self,
    index: &Index,
    repository: &Repository,
) -> Vec<(FileId, FileId)>
```

Returns directed `(importer, dependency)` file edges within the index.

<details>
<summary>Source</summary>

```rust
    fn resolve_dependencies(&self, index: &Index, repository: &Repository)
```

</details>

### <span id="trait.Language"></span><code style="font-size: 0.85em">trait Language</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Supertraits:** `Debug + Send + Sync`

Language-specific parsing, outline rendering, and package resolution.

#### Methods

##### <span id="Language.id"></span><code>id</code>

```rust
fn id(&self) -> &'static str
```

Returns the stable language ID used by the index and analysis maps.

<details>
<summary>Source</summary>

```rust
    fn id(&self) -> &'static str;
```

</details>

##### <span id="Language.package_language"></span><code>package_​language</code>

```rust
fn package_language(&self) -> &'static str
```

Dialects with different grammars can share project ownership.

<details>
<summary>Source</summary>

```rust
    fn package_language(&self) -> &'static str {
        self.id()
    }
```

</details>

##### <span id="Language.grammar"></span><code>grammar</code>

```rust
fn grammar(&self) -> ts::Language
```

Returns the Tree-sitter grammar used to parse source.

<details>
<summary>Source</summary>

```rust
    fn grammar(&self) -> ts::Language;
```

</details>

##### <span id="Language.source_query"></span><code>source_​query</code>

```rust
fn source_query(&self) -> &'static str
```

Returns the Tree-sitter query for outline and dependency captures.

<details>
<summary>Source</summary>

```rust
    fn source_query(&self) -> &'static str;
```

</details>

##### <span id="Language.query"></span><code>query</code>

```rust
fn query(&self) -> Result<ts::Query, Error>
```

Compiles the outline and dependency query for this grammar.

**Errors:**

Returns an error if the query is invalid for the grammar.

<details>
<summary>Source</summary>

```rust
    fn query(&self) -> Result<ts::Query, Error> {
        Ok(ts::Query::new(&self.grammar(), self.source_query())?)
    }
```

</details>

##### <span id="Language.create_analysis"></span><code>create_​analysis</code>

```rust
fn create_analysis(&self) -> Box<dyn LanguageAnalysis>
```

Creates repository-local dependency state shared by parallel file analysis.

<details>
<summary>Source</summary>

```rust
    fn create_analysis(&self) -> Box<dyn LanguageAnalysis>;
```

</details>

##### <span id="Language.allow_partial_analysis"></span><code>allow_​partial_​analysis</code>

```rust
fn allow_partial_analysis(&self) -> bool
```

Allows outlines from recovered syntax trees. Defaults to `true`.

<details>
<summary>Source</summary>

```rust
    fn allow_partial_analysis(&self) -> bool {
        true
    }
```

</details>

##### <span id="Language.supplement_analysis"></span><code>supplement_​analysis</code>

```rust
fn supplement_analysis(
    &self,
    _file: FileId,
    _root: ts::Node<'_>,
    _source: &[u8],
    _analysis: &mut Analysis,
)
```

Adds ranges for embedded languages or narrowly supported grammar extensions.

<details>
<summary>Source</summary>

```rust
    fn supplement_analysis(
        &self,
        _file: FileId,
        _root: ts::Node<'_>,
        _source: &[u8],
        _analysis: &mut Analysis,
    ) {
    }
```

</details>

##### <span id="Language.analyze"></span><code>analyze</code>

```rust
fn analyze(
    &self,
    file: FileId,
    parser: &mut ts::Parser,
    query: &ts::Query,
    source: &[u8],
    state: &dyn LanguageAnalysis,
) -> Result<Analysis, Error>
```

Captures outline ranges and records dependencies in repository-local state.

The query must be compiled for this language's grammar. Returned ranges
are sorted and deduplicated byte offsets into `source`; overlapping ranges
are retained. The parser can be reused for subsequent files.

**Errors:**

Returns an error if the parser cannot use the grammar or produce a tree.

<details>
<summary>Source</summary>

```rust
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
```

</details>

##### <span id="Language.render_sigs"></span><code>render_​sigs</code>

```rust
fn render_sigs(&self, source: &str, analysis: &Analysis) -> String
```

Render a declaration outline, not necessarily executable source.

<details>
<summary>Source</summary>

```rust
    fn render_sigs(&self, source: &str, analysis: &Analysis) -> String {
        render_spans(source, analysis.imports.iter().chain(&analysis.sigs), true)
    }
```

</details>

##### <span id="Language.render_skel"></span><code>render_​skel</code>

```rust
fn render_skel(&self, source: &str, analysis: &Analysis) -> String
```

Render a documented outline without reparsing the source.

<details>
<summary>Source</summary>

```rust
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
```

</details>

##### <span id="Language.is_package_manifest"></span><code>is_​package_​manifest</code>

```rust
fn is_package_manifest(
    &self,
    _index: &Index,
    _path: &Path,
    _config: &Config,
) -> Result<bool, Error>
```

Checks whether a matching marker is a real package boundary.

The default accepts every marker.

**Errors:**

Returns an error if inspecting the candidate manifest fails.

<details>
<summary>Source</summary>

```rust
    fn is_package_manifest(
        &self,
        _index: &Index,
        _path: &Path,
        _config: &Config,
    ) -> Result<bool, Error> {
        Ok(true)
    }
```

</details>

##### <span id="Language.discover_packages"></span><code>discover_​packages</code>

```rust
fn discover_packages(
    &self,
    index: &Index,
    config: &Config,
) -> Result<Vec<Package>, Error>
```

Groups accepted package markers by their parent directory.

**Errors:**

Returns an error if inspecting a candidate manifest fails.

<details>
<summary>Source</summary>

```rust
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
```

</details>

##### <span id="Language.resolve_packages"></span><code>resolve_​packages</code>

```rust
fn resolve_packages(
    &mut self,
    index: &Index,
    config: &Config,
) -> Result<PackageResolution, Error>
```

Resolves local packages after package IDs and file ownership are assigned.

**Errors:**

Returns an error if package metadata cannot be read or parsed.

<details>
<summary>Source</summary>

```rust
    fn resolve_packages(
```

</details>

##### <span id="Language.resolve_dependencies"></span><code>resolve_​dependencies</code>

```rust
fn resolve_dependencies(
    &self,
    index: &Index,
    repository: &Repository,
) -> Vec<(FileId, FileId)>
```

Resolves local file dependencies from the repository's language state.

Returns an empty list when no analysis exists for this language.

<details>
<summary>Source</summary>

```rust
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
```

</details>

##### <span id="Language.ignore_patterns"></span><code>ignore_​patterns</code>

```rust
fn ignore_patterns(&self) -> &'static [&'static str]
```

Uses `ignore::overrides` syntax: `!` prefixes exclusions.

<details>
<summary>Source</summary>

```rust
    fn ignore_patterns(&self) -> &'static [&'static str];
```

</details>

##### <span id="Language.package_markers"></span><code>package_​markers</code>

```rust
fn package_markers(&self) -> &'static [&'static str]
```

Returns filenames that may establish package boundaries.

<details>
<summary>Source</summary>

```rust
    fn package_markers(&self) -> &'static [&'static str];
```

</details>

##### <span id="Language.package_metadata_files"></span><code>package_​metadata_​files</code>

```rust
fn package_metadata_files(&self) -> &'static [&'static str]
```

Returns recognized package and tool metadata filenames.

This metadata list does not itself control scanning exclusions.

<details>
<summary>Source</summary>

```rust
    fn package_metadata_files(&self) -> &'static [&'static str];
```

</details>

##### <span id="Language.matches_filename"></span><code>matches_​filename</code>

```rust
fn matches_filename(&self, _name: &str) -> bool
```

Recognizes conventional source filenames before extension-based detection.

<details>
<summary>Source</summary>

```rust
    fn matches_filename(&self, _name: &str) -> bool {
        false
    }
```

</details>

##### <span id="Language.file_extensions"></span><code>file_​extensions</code>

```rust
fn file_extensions(&self) -> &'static [&'static str]
```

Returns recognized, case-sensitive source extensions, including the leading dot.

<details>
<summary>Source</summary>

```rust
    fn file_extensions(&self) -> &'static [&'static str];
```

</details>
