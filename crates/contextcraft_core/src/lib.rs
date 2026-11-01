//! AST-aware, personalized-PageRank-ranked, token-budgeted codebase compression for LLMs.
//!
//! [`ContextCraft::run`] indexes local packages, reads and redacts source files,
//! resolves dependencies, ranks files, and selects a fidelity level for each file.
//! The individual pipeline stages are also available through their modules.
//!
//! Pipeline data uses public fields rather than accessors. File and package IDs
//! belong to the index that created them. Keep IDs and language registrations
//! consistent when editing data, and rebuild downstream stages after changes.
//!
//! ```no_run
//! use contextcraft_core::{Config, ContextCraft};
//!
//! let analysis = ContextCraft::new(Config::default()).run(".")?;
//! println!("{}", analysis.artifact.content);
//! # Ok::<(), contextcraft_core::error::Error>(())
//! ```

use std::num::NonZeroUsize;
use std::path::Path;

use la_arena::ArenaMap;

use crate::error::Error;
use crate::formatter::{Artifact, ArtifactFormatter};
use crate::graph::{Graph, GraphScorer};
use crate::index::{FileId, Index, Indexer};
use crate::optimizer::BudgetAllocator;
use crate::repo::{Repository, RepositoryReader};
use crate::tiers::{TierRenderer, Tiers};

pub mod error;
pub mod formatter;
pub mod graph;
pub mod index;
pub mod languages;
pub mod optimizer;
pub mod package;
pub mod repo;
pub mod tiers;
pub mod tokens;

/// Intermediate pipeline data and the final budgeted artifact.
pub struct RepositoryAnalysis {
    /// Indexed files, package ownership, and language implementations.
    pub index: Index,
    /// Readable source files and extracted language state.
    pub repository: Repository,
    /// Directed local file dependencies used for ranking.
    pub graph: Graph,
    /// Normalized relevance scores keyed by this analysis's file IDs.
    pub scores: ArenaMap<FileId, f64>,
    /// Rendered fidelity tiers with lazily cached token costs.
    pub tiers: Tiers,
    /// Final serialized context and its token count.
    pub artifact: Artifact,
}

/// Repository compression pipeline configured with [`Config`].
#[derive(Debug, Default)]
pub struct ContextCraft {
    /// Settings used by the next call to [`Self::run`].
    pub config: Config,
}

impl ContextCraft {
    /// Creates a pipeline with the supplied configuration.
    pub fn new(config: Config) -> Self {
        Self { config }
    }

    /// Analyzes a local repository and renders its compressed context.
    ///
    /// Each call reads and analyzes the repository again.
    ///
    /// # Errors
    ///
    /// Returns an error if the root is not a directory, repository access or
    /// manifest parsing fails, source analysis fails, or output framing cannot
    /// fit within the token budget.
    pub fn run(&self, root: impl AsRef<Path>) -> Result<RepositoryAnalysis, Error> {
        let index = Indexer::new().index(root, &self.config)?;
        let repository = RepositoryReader::new().read(&index, &self.config)?;
        let graph = Graph::new(&index, &repository);
        let scores = GraphScorer::score(&index, &repository, &graph, &self.config);
        let tiers = TierRenderer::render(&index, &repository, &self.config)?;
        let selection = BudgetAllocator::allocate(&index, &tiers, &scores, &self.config)?;
        let artifact =
            ArtifactFormatter::format(&index, &tiers, &scores, &selection, &self.config)?;

        Ok(RepositoryAnalysis {
            index,
            repository,
            graph,
            scores,
            tiers,
            artifact,
        })
    }
}

/// Serialization format for the generated artifact.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    /// Markdown headings and fenced source blocks. The default format.
    #[default]
    Markdown,
    /// XML elements with escaped paths and source content.
    Xml,
    /// JSON containing a path listing and selected file blocks.
    Json,
}

impl OutputFormat {
    /// Returns the identifier used in configuration and serialized output.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Markdown => "markdown",
            Self::Xml => "xml",
            Self::Json => "json",
        }
    }
}

/// Tokenizer vocabulary used to measure the output budget.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum TokenizerEncoding {
    /// Original GPT-2 vocabulary, named `gpt2`.
    Gpt2,
    /// GPT-3 vocabulary, named `r50k_base`.
    R50kBase,
    /// Codex vocabulary, named `p50k_base`.
    P50kBase,
    /// Edit-model vocabulary, named `p50k_edit`.
    P50kEdit,
    /// Vocabulary named `cl100k_base`. The default encoding.
    #[default]
    Cl100kBase,
    /// Vocabulary named `o200k_base`.
    O200kBase,
    /// Harmony vocabulary, named `o200k_harmony`.
    O200kHarmony,
}

impl TokenizerEncoding {
    /// Returns the identifier used in configuration and serialized output.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Gpt2 => "gpt2",
            Self::R50kBase => "r50k_base",
            Self::P50kBase => "p50k_base",
            Self::P50kEdit => "p50k_edit",
            Self::Cl100kBase => "cl100k_base",
            Self::O200kBase => "o200k_base",
            Self::O200kHarmony => "o200k_harmony",
        }
    }
}

/// Repository scanning, ranking, and output settings.
///
/// Construct custom settings with struct update syntax to retain other defaults.
///
/// ```
/// use std::num::NonZeroUsize;
/// use contextcraft_core::{Config, ContextCraft, OutputFormat};
///
/// let mut pipeline = ContextCraft::new(Config {
///     budget_tokens: NonZeroUsize::new(8_000).unwrap(),
///     output_format: OutputFormat::Json,
///     ..Config::default()
/// });
/// pipeline.config.focus_query = Some("authentication".into());
/// ```
#[derive(Debug, Clone)]
pub struct Config {
    /// Runs source analysis and tier rendering with Rayon. Defaults to `true`.
    pub enable_parallel: bool,
    /// Maximum token count for the complete serialized artifact.
    ///
    /// Defaults to 16,000. Rendering fails if even empty output framing cannot fit.
    pub budget_tokens: NonZeroUsize,
    /// Task description used for lexical relevance and personalized ranking.
    ///
    /// Defaults to `None`, leaving ranking unbiased by a text query.
    pub focus_query: Option<String>,
    /// Paths, directories, filenames, or globs to favor during ranking.
    ///
    /// Directory matches respect path boundaries. Wildcards may span separators.
    /// Defaults to an empty list. Matching files are favored, not guaranteed inclusion.
    pub focus_files: Vec<String>,
    /// Artifact serialization format. Defaults to [`OutputFormat::Markdown`].
    pub output_format: OutputFormat,
    /// Exclusions in `ignore::overrides` glob syntax, without the `!` prefix.
    ///
    /// Paths are relative to the repository root. Defaults to an empty list.
    pub exclude_patterns: Vec<String>,
    /// Honors repository, global, and explicit Git exclusion rules.
    ///
    /// Defaults to `true`. Language-specific exclusions still apply when disabled.
    pub respect_gitignore: bool,
    /// Replaces recognized secrets before source analysis and rendering.
    ///
    /// Defaults to `true`. Replacement preserves byte offsets and line breaks.
    /// Detection is limited to configured secret types, not every possible secret.
    pub redact_secrets: bool,
    /// Maximum source size to read. Larger files remain available as paths only.
    ///
    /// Also bounds manifest reads. Defaults to 1,048,576 bytes (1 MiB).
    pub max_file_size_bytes: NonZeroUsize,
    /// Vocabulary used for token costs. Defaults to [`TokenizerEncoding::Cl100kBase`].
    pub tokenizer_encoding: TokenizerEncoding,
    /// Permits estimated counts supplied to individual pipeline stages.
    ///
    /// Defaults to `true`. The current tokenizer always counts exactly and does
    /// not use a fallback.
    pub allow_token_estimates: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            enable_parallel: true,
            budget_tokens: NonZeroUsize::new(16_000).unwrap(),
            focus_query: None,
            focus_files: Vec::new(),
            output_format: OutputFormat::default(),
            exclude_patterns: Vec::new(),
            respect_gitignore: true,
            redact_secrets: true,
            max_file_size_bytes: NonZeroUsize::new(1_048_576).unwrap(),
            tokenizer_encoding: TokenizerEncoding::default(),
            allow_token_estimates: true,
        }
    }
}
