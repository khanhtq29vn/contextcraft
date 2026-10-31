---
title: "contextcraft-ai-core::graph::scorer"
description: "API reference of the Rust module contextcraft-ai-core::graph::scorer."
editUrl: false
sidebar:
  order: 10
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

## Structs

### <span id="struct.GraphScorer"></span><code style="font-size: 0.85em">struct GraphScorer</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Ranks files with personalized PageRank and field-weighted lexical relevance.

#### Methods

##### <span id="GraphScorer.score"></span><code>score</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

```rust
fn score(
    index: &Index,
    repository: &Repository,
    graph: &Graph,
    config: &Config,
) -> ArenaMap<FileId, f64>
```

Returns normalized file scores biased toward the configured focus.

Combines field-weighted BM25 relevance and focused paths with dependency
ranking. Empty indexes produce an empty score map.

**Panics:**

Panics if focus-file patterns are configured and an indexed path has no
filename, or if a dependency of an indexed file is outside the index.

<details>
<summary>Source</summary>

```rust
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
```

</details>
