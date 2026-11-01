//! Render escaped Markdown, XML, or JSON and enforce the final token budget.

use std::collections::HashSet;
use std::io::{self, Write};

use la_arena::ArenaMap;

use crate::error::Error;
use crate::index::{FileId, Index};
use crate::optimizer::{Selection, validate_scores};
use crate::tiers::{FidelityLevel, Tiers};
use crate::tokens::TokenCounter;
use crate::{Config, OutputFormat};

/// Serialized repository context and the fidelity levels included in it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Artifact {
    /// Complete serialized context, including path listings and framing.
    pub content: String,
    /// Token count for the complete serialized content.
    pub tokens: usize,
    /// Whether any input or final token count used an estimate.
    pub token_counts_estimated: bool,
    /// Final fidelity level for every indexed file, including path-only files.
    pub selected_tiers: ArenaMap<FileId, FidelityLevel>,
}

/// Serializes selected tiers and downgrades them if the final output is too large.
#[derive(Debug)]
pub struct ArtifactFormatter;

impl ArtifactFormatter {
    /// Renders one escaped file block. The path-only tier produces no block.
    ///
    /// # Examples
    ///
    /// JSON output escapes source text so the block can be parsed independently.
    ///
    /// ```
    /// use contextcraft_core::OutputFormat;
    /// use contextcraft_core::formatter::ArtifactFormatter;
    /// use contextcraft_core::tiers::FidelityLevel;
    ///
    /// let block = ArtifactFormatter::render_file(
    ///     "src/main.rs",
    ///     "fn main() { println!(\"hello\"); }\n",
    ///     FidelityLevel::Full,
    ///     OutputFormat::Json,
    /// );
    /// let file: serde_json::Value = serde_json::from_str(&block)?;
    /// assert_eq!(file["path"], "src/main.rs");
    /// assert_eq!(file["content"], "fn main() { println!(\"hello\"); }\n");
    /// # Ok::<(), serde_json::Error>(())
    /// ```
    pub fn render_file(
        path: &str,
        content: &str,
        level: FidelityLevel,
        format: OutputFormat,
    ) -> String {
        if level == FidelityLevel::Tree {
            return String::new();
        }

        let mut output = Vec::with_capacity(content.len() + path.len() + 64);
        render_file_into(&mut output, path, content, level, format)
            .expect("writing to a Vec cannot fail");
        String::from_utf8(output).expect("file framing preserves UTF-8")
    }

    pub(crate) fn file_bytes(
        path: &str,
        content: &str,
        level: FidelityLevel,
        format: OutputFormat,
    ) -> usize {
        let mut counter = ByteCounter(0);
        render_file_into(&mut counter, path, content, level, format)
            .expect("counting bytes cannot fail");
        counter.0
    }

    /// Counts a framed file block, including a trailing comma for JSON.
    ///
    /// The path-only tier costs zero here because paths are budgeted separately.
    /// Joined blocks must be recounted because BPE merges can span their boundaries.
    ///
    /// # Errors
    ///
    /// Propagates token-counting failures.
    pub fn file_cost(
        path: &str,
        content: &str,
        level: FidelityLevel,
        counter: &TokenCounter,
        format: OutputFormat,
    ) -> Result<usize, Error> {
        if level == FidelityLevel::Tree {
            return Ok(0);
        }

        let mut block = Self::render_file(path, content, level, format);

        if format == OutputFormat::Json {
            block.push(',');
        }

        counter.count(&block)
    }

    /// Serializes a selection and path listing without enforcing a token budget.
    ///
    /// Writes escaped paths and file blocks directly into one output buffer.
    ///
    /// # Errors
    ///
    /// Returns an error for inconsistent pipeline inputs, duplicate paths, or
    /// paths that do not belong to the index.
    pub fn render(
        index: &Index,
        tiers: &Tiers,
        selection: &Selection,
        tree: &[FileId],
        config: &Config,
    ) -> Result<String, Error> {
        tiers.validate(index, config)?;
        selection.validate(index, tiers)?;
        let mut seen = HashSet::new();

        if tree
            .iter()
            .any(|&file| tiers.files.get(file).is_none() || !seen.insert(file))
        {
            return Err(Error::InvalidPipeline(
                "path listings must contain unique indexed files",
            ));
        }

        let mut output = Vec::new();
        render_into(
            &mut output,
            index,
            tiers,
            selection,
            tree,
            config.output_format,
        )
        .expect("writing to a Vec cannot fail");
        Ok(String::from_utf8(output).expect("repository framing preserves UTF-8"))
    }

    /// Selects an index-ordered path listing using up to a tenth of the budget.
    ///
    /// # Errors
    ///
    /// Returns an error for inconsistent pipeline inputs, token-counting failures,
    /// or a budget smaller than the empty output framing.
    pub fn directory_tree(
        index: &Index,
        tiers: &Tiers,
        counter: &TokenCounter,
        config: &Config,
    ) -> Result<Vec<FileId>, Error> {
        let selection = Selection {
            tiers: index
                .files
                .iter()
                .map(|(file, _)| (file, FidelityLevel::Tree))
                .collect(),
            token_counts_estimated: tiers.token_counts_estimated,
        };
        let baseline = counter.count(&Self::render(index, tiers, &selection, &[], config)?)?;

        if baseline > config.budget_tokens.get() {
            return Err(Error::BudgetTooSmall {
                budget: config.budget_tokens.get(),
                minimum: baseline,
            });
        }

        let mut paths: Vec<_> = index.files.iter().map(|(file, _)| file).collect();
        let mut low = 0;
        let mut high = paths.len();

        while low < high {
            let middle = low + (high - low).div_ceil(2);
            let cost = counter.count(&Self::render(
                index,
                tiers,
                &selection,
                &paths[..middle],
                config,
            )?)?;

            if cost.saturating_sub(baseline) <= config.budget_tokens.get() / 10 {
                low = middle;
            } else {
                high = middle - 1;
            }
        }

        paths.truncate(low);
        paths.shrink_to_fit();
        Ok(paths)
    }

    /// Renders a selection and downgrades tiers until the output fits the budget.
    ///
    /// Recounts the complete output after each downgrade to account for token
    /// boundaries between file blocks.
    ///
    /// # Errors
    ///
    /// Returns an error for inconsistent inputs, invalid scores, token-counting
    /// failures, or a budget smaller than the output framing.
    pub fn format(
        index: &Index,
        tiers: &Tiers,
        scores: &ArenaMap<FileId, f64>,
        selection: &Selection,
        config: &Config,
    ) -> Result<Artifact, Error> {
        tiers.validate(index, config)?;
        selection.validate(index, tiers)?;
        validate_scores(index, scores)?;

        if selection.token_counts_estimated && !config.allow_token_estimates {
            return Err(Error::InvalidPipeline(
                "strict counting requires an exact allocation",
            ));
        }

        let counter = TokenCounter::new(config.tokenizer_encoding, config.allow_token_estimates)?;
        let mut selected = selection.clone();
        let mut tree = Self::directory_tree(index, tiers, &counter, config)?;

        loop {
            let content = Self::render(index, tiers, &selected, &tree, config)?;
            let tokens = counter.count(&content)?;

            if tokens <= config.budget_tokens.get() {
                return Ok(Artifact {
                    content,
                    tokens,
                    token_counts_estimated: tiers.token_counts_estimated
                        || selected.token_counts_estimated
                        || counter.used_estimates(),
                    selected_tiers: selected.tiers,
                });
            }

            // Release oversized output before counting replacement tiers.
            drop(content);

            let mut best: Option<(f64, f64, FileId, FidelityLevel)> = None;

            for (file, &current) in selected.tiers.iter() {
                let path = &tiers.files[file].levels[FidelityLevel::Tree as usize]
                    .as_ref()
                    .unwrap()
                    .content;
                let current_tier = tiers.files[file].levels[current as usize].as_ref().unwrap();
                let current_cost =
                    current_tier.count(path, current, &counter, config.output_format)?;

                for lower in FidelityLevel::ALL
                    .into_iter()
                    .filter(|&level| level < current)
                {
                    let Some(tier) = tiers.files[file].levels[lower as usize].as_ref() else {
                        continue;
                    };
                    let cost = tier.count(path, lower, &counter, config.output_format)?;
                    let savings = current_cost.saturating_sub(cost);

                    if savings == 0 {
                        continue;
                    }

                    let loss =
                        scores[file] * (current.semantic_utility() - lower.semantic_utility());
                    let candidate = (loss / savings as f64, loss, file, lower);

                    if best.as_ref().is_none_or(|best| {
                        candidate
                            .0
                            .total_cmp(&best.0)
                            .then_with(|| candidate.1.total_cmp(&best.1))
                            .then_with(|| candidate.2.cmp(&best.2))
                            .then_with(|| candidate.3.cmp(&best.3))
                            .is_lt()
                    }) {
                        best = Some(candidate);
                    }
                }
            }

            if let Some((_, _, file, lower)) = best {
                selected.tiers[file] = lower;
            } else if !tree.is_empty() {
                tree.truncate(tree.len() / 2);
            } else {
                return Err(Error::BudgetTooSmall {
                    budget: config.budget_tokens.get(),
                    minimum: tokens,
                });
            }
        }
    }
}

fn render_into(
    output: &mut impl Write,
    index: &Index,
    tiers: &Tiers,
    selection: &Selection,
    tree: &[FileId],
    format: OutputFormat,
) -> io::Result<()> {
    let path = |file| {
        tiers.files[file].levels[FidelityLevel::Tree as usize]
            .as_ref()
            .unwrap()
            .content
            .as_ref()
    };
    let omitted = index.files.len() - tree.len();

    match format {
        OutputFormat::Json => {
            output.write_all(b"{\"tree\":[")?;

            for (position, &file) in tree.iter().enumerate() {
                if position != 0 {
                    output.write_all(b",")?;
                }
                write_json(output, path(file))?;
            }

            write!(output, "],\"omitted_paths\":{omitted},\"files\":[")?;
        }
        OutputFormat::Xml => {
            write!(
                output,
                "<repository_context><tree omitted_paths=\"{omitted}\""
            )?;

            if tree.is_empty() {
                output.write_all(b" />")?;
            } else {
                output.write_all(b">")?;

                for &file in tree {
                    output.write_all(b"<file path=\"")?;
                    write_xml(output, path(file), true)?;
                    output.write_all(b"\" />")?;
                }

                output.write_all(b"</tree>")?;
            }

            output.write_all(b"<files>")?;
        }
        OutputFormat::Markdown => {
            output.write_all(b"# Repository context\n\n")?;

            for &file in tree {
                output.write_all(b"- ")?;
                write_json(output, path(file))?;
                output.write_all(b"\n")?;
            }

            if omitted != 0 {
                writeln!(output, "- {omitted} paths omitted")?;
            }

            if !tree.is_empty() || omitted != 0 {
                output.write_all(b"\n")?;
            }
        }
    }

    let mut first = true;

    for (file, _) in index.files.iter() {
        let level = selection.tiers[file];

        if level == FidelityLevel::Tree {
            continue;
        }

        if format == OutputFormat::Json && !first {
            output.write_all(b",")?;
        }
        first = false;

        let content = &tiers.files[file].levels[level as usize]
            .as_ref()
            .unwrap()
            .content;
        render_file_into(output, path(file), content, level, format)?;
    }

    match format {
        OutputFormat::Json => output.write_all(b"]}"),
        OutputFormat::Xml => output.write_all(b"</files></repository_context>"),
        OutputFormat::Markdown => Ok(()),
    }
}

// Share framing with rendering without collecting the complete file block.
struct ByteCounter(usize);

impl Write for ByteCounter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0 += bytes.len();
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn render_file_into(
    output: &mut impl Write,
    path: &str,
    content: &str,
    level: FidelityLevel,
    format: OutputFormat,
) -> io::Result<()> {
    if level == FidelityLevel::Tree {
        return Ok(());
    }

    match format {
        OutputFormat::Json => {
            output.write_all(b"{\"path\":")?;
            write_json(output, path)?;
            write!(output, ",\"tier\":\"{}\",\"content\":", level.as_str())?;
            write_json(output, content)?;
            output.write_all(b"}")
        }
        OutputFormat::Xml => {
            output.write_all(b"<file path=\"")?;
            write_xml(output, path, true)?;
            write!(output, "\" tier=\"{}\"", level.as_str())?;

            if content.is_empty() {
                output.write_all(b" />")
            } else {
                output.write_all(b">")?;
                write_xml(output, content, false)?;
                output.write_all(b"</file>")
            }
        }
        OutputFormat::Markdown => {
            let mut longest = 0;
            let mut run = 0;

            for byte in content.bytes() {
                if byte == b'`' {
                    run += 1;
                    longest = longest.max(run);
                } else {
                    run = 0;
                }
            }

            let fence = "`".repeat(3.max(longest + 1));
            output.write_all(b"## ")?;
            write_json(output, path)?;
            write!(
                output,
                " [{}]\n\n{fence}\n{content}\n{fence}\n\n",
                level.as_str()
            )
        }
    }
}

fn write_json(output: &mut impl Write, text: &str) -> io::Result<()> {
    serde_json::to_writer(output, text).map_err(io::Error::other)
}

fn write_xml(output: &mut impl Write, text: &str, attribute: bool) -> io::Result<()> {
    let mut start = 0;

    for (offset, character) in text.char_indices() {
        let replacement = match character {
            '&' => "&amp;",
            '<' => "&lt;",
            '>' => "&gt;",
            '"' if attribute => "&quot;",
            '\'' if attribute => "&apos;",
            '\n' if attribute => "&#10;",
            '\t' if attribute => "&#9;",
            '\r' => "&#13;",
            '\u{0}'..='\u{8}'
            | '\u{b}'
            | '\u{c}'
            | '\u{e}'..='\u{1f}'
            | '\u{fffe}'
            | '\u{ffff}' => "\u{fffd}",
            _ => continue,
        };

        output.write_all(&text.as_bytes()[start..offset])?;
        output.write_all(replacement.as_bytes())?;
        start = offset + character.len_utf8();
    }

    output.write_all(&text.as_bytes()[start..])
}
