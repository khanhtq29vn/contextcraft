//! Errors reported by repository analysis and artifact generation.

use std::io;
use std::path::PathBuf;

use tree_sitter as ts;

/// Failures callers can distinguish when running individual pipeline stages.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// A repository file or directory could not be accessed.
    #[error("failed to access {}: {source}", path.display())]
    Io {
        /// Path associated with the failed operation.
        path: PathBuf,
        /// Underlying filesystem error.
        #[source]
        source: io::Error,
    },

    /// The requested repository root is not a directory.
    #[error("not a directory: {}", .0.display())]
    NotADirectory(PathBuf),

    /// Directory traversal or exclusion-pattern compilation failed.
    #[error(transparent)]
    Ignore(#[from] ignore::Error),

    /// A language query is invalid for its grammar.
    #[error(transparent)]
    Query(#[from] ts::QueryError),

    /// The parser could not load a language grammar.
    #[error(transparent)]
    Language(#[from] ts::LanguageError),

    /// A package or workspace manifest is invalid.
    #[error("invalid manifest {}: {message}", path.display())]
    Manifest {
        /// Manifest path relative to the repository root.
        path: PathBuf,
        /// Parsing or resolution diagnostic.
        message: String,
    },

    /// The parser did not produce a syntax tree.
    #[error("parser did not produce a syntax tree")]
    Parse,

    /// Individually supplied pipeline inputs violate a consistency requirement.
    #[error("invalid pipeline input: {0}")]
    InvalidPipeline(&'static str),

    /// Output framing cannot fit within the requested token budget.
    #[error("token budget {budget} is smaller than the minimum output framing ({minimum} tokens)")]
    BudgetTooSmall {
        /// Requested maximum token count.
        budget: usize,
        /// Token count of the smallest output reached by the formatter.
        minimum: usize,
    },

    /// The configured tokenizer is unavailable or could not count tokens.
    #[error("tokenization failed for {encoding}: {message}")]
    Tokenization {
        /// Requested tokenizer vocabulary identifier.
        encoding: &'static str,
        /// Tokenizer diagnostic.
        message: String,
    },
}
