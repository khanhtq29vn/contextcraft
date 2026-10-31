//! Render reusable fidelity tiers and lazily cache their framed token costs.

use std::sync::{Arc, OnceLock};

use la_arena::ArenaMap;
use rayon::prelude::*;

use crate::error::Error;
use crate::formatter::ArtifactFormatter;
use crate::index::{File, FileId, Index};
use crate::repo::Repository;
use crate::tokens::TokenCounter;
use crate::{Config, OutputFormat, TokenizerEncoding};

/// Increasing levels of source detail available to the budget allocator.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(usize)]
pub enum FidelityLevel {
    /// Path-only listing with no source block.
    Tree,
    /// Declaration headers and imports, with richer content as a fallback.
    Sigs,
    /// Documented declaration outline, with full content as a fallback.
    Skel,
    /// Complete readable source after optional secret redaction.
    Full,
}

impl FidelityLevel {
    /// All levels in increasing fidelity order.
    pub const ALL: [Self; 4] = [Self::Tree, Self::Sigs, Self::Skel, Self::Full];

    /// Returns the allocator's relative utility weight, from `0.0` to `1.0`.
    pub fn semantic_utility(self) -> f64 {
        match self {
            Self::Tree => 0.0,
            Self::Sigs => 0.45,
            Self::Skel => 0.82,
            Self::Full => 1.0,
        }
    }

    /// Returns the uppercase label used in serialized file blocks.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Tree => "TREE",
            Self::Sigs => "SIGS",
            Self::Skel => "SKEL",
            Self::Full => "FULL",
        }
    }
}

/// Shared tier content with a lazily counted framed token cost.
///
/// Cloning shares the content but copies the current token-cost cache. Concurrent
/// readers may compute the same cost before one result is cached. Cached costs
/// apply only to the path, fidelity level, format, and encoding used to count them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RenderedTier {
    /// Rendered source outline, full source, or path for the path-only tier.
    ///
    /// Do not replace content after its framed token cost has been cached.
    pub content: Arc<str>,
    estimated_framed_tokens: usize,
    framed_tokens: OnceLock<usize>,
}

impl RenderedTier {
    fn new(content: Arc<str>, path: &str, level: FidelityLevel, format: OutputFormat) -> Self {
        let block = ArtifactFormatter::render_file(path, &content, level, format);
        let bytes = block.len() + usize::from(format == OutputFormat::Json);

        Self {
            content,
            estimated_framed_tokens: bytes.div_ceil(4),
            framed_tokens: OnceLock::new(),
        }
    }

    /// Returns the exact framed cost if cached, otherwise a byte-based estimate.
    pub fn framed_tokens(&self) -> usize {
        self.framed_tokens
            .get()
            .copied()
            .unwrap_or(self.estimated_framed_tokens)
    }

    pub(crate) fn is_counted(&self) -> bool {
        self.framed_tokens.get().is_some()
    }

    pub(crate) fn count(
        &self,
        path: &str,
        level: FidelityLevel,
        counter: &TokenCounter,
        format: OutputFormat,
    ) -> Result<usize, Error> {
        if let Some(&tokens) = self.framed_tokens.get() {
            return Ok(tokens);
        }

        let tokens = ArtifactFormatter::file_cost(path, &self.content, level, counter, format)?;
        let _ = self.framed_tokens.set(tokens);
        Ok(tokens)
    }
}

/// Available fidelity tiers for one indexed file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileTiers {
    /// Tiers indexed by `FidelityLevel as usize`, from path-only to full source.
    pub levels: [Option<RenderedTier>; 4],
}

/// Per-file tiers tied to one output format and tokenizer encoding.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Tiers {
    /// Serialization format used to frame and cost these tiers.
    pub output_format: OutputFormat,
    /// Vocabulary used for cached exact token costs.
    pub tokenizer_encoding: TokenizerEncoding,
    /// Whether the tier costs include fallback token estimates.
    pub token_counts_estimated: bool,
    /// Available tiers keyed by IDs from the associated index.
    pub files: ArenaMap<FileId, FileTiers>,
}

impl Tiers {
    pub(crate) fn validate(&self, index: &Index, config: &Config) -> Result<(), Error> {
        if self.output_format != config.output_format
            || self.tokenizer_encoding != config.tokenizer_encoding
        {
            return Err(Error::InvalidPipeline(
                "tier format or encoding differs from the configuration",
            ));
        }

        if self.token_counts_estimated && !config.allow_token_estimates {
            return Err(Error::InvalidPipeline(
                "strict counting requires exact tier costs",
            ));
        }

        if self.files.iter().count() != index.files.len()
            || index.files.iter().any(|(file, _)| {
                self.files
                    .get(file)
                    .and_then(|tiers| tiers.levels[FidelityLevel::Tree as usize].as_ref())
                    .is_none()
            })
        {
            return Err(Error::InvalidPipeline(
                "render tiers for every indexed file first",
            ));
        }

        Ok(())
    }
}

/// Builds outlines from captured byte ranges without reparsing source.
#[derive(Debug)]
pub struct TierRenderer;

impl TierRenderer {
    /// Renders tiers, using a placeholder when a supported language has no outline.
    /// Unsupported files retain the richer-source fallback.
    ///
    /// Files without readable source receive only a path-only tier.
    ///
    /// # Errors
    ///
    /// This implementation does not return errors.
    ///
    /// # Panics
    ///
    /// Panics if manually edited sources are not UTF-8 or a parsed file refers
    /// to a language missing from the index.
    pub fn render(index: &Index, repository: &Repository, config: &Config) -> Result<Tiers, Error> {
        let render_file = |(file_id, file): (FileId, &File)| {
            let path = file
                .path
                .to_string_lossy()
                .replace(std::path::MAIN_SEPARATOR, "/");
            let tree = RenderedTier {
                content: Arc::from(path.as_str()),
                // Path listings are budgeted separately from file blocks.
                estimated_framed_tokens: 0,
                framed_tokens: OnceLock::from(0),
            };
            let mut levels = [Some(tree), None, None, None];

            if let Some(source) = repository.sources.get(file_id) {
                let content =
                    std::str::from_utf8(&source.bytes).expect("repository source is UTF-8");
                let full = RenderedTier::new(
                    Arc::from(content),
                    &path,
                    FidelityLevel::Full,
                    config.output_format,
                );
                levels[FidelityLevel::Full as usize] = Some(full);

                for (level, richer) in [
                    (FidelityLevel::Skel, FidelityLevel::Full),
                    (FidelityLevel::Sigs, FidelityLevel::Skel),
                ] {
                    let rendered = if let (Some(language), Some(analysis)) =
                        (file.language, source.analysis.as_ref())
                    {
                        let language = &index.languages[language];

                        let outline = if level == FidelityLevel::Skel {
                            language.render_skel(content, analysis)
                        } else {
                            language.render_sigs(content, analysis)
                        };

                        if outline.trim().is_empty() {
                            "Outline unavailable; use FULL for source.".into()
                        } else {
                            outline
                        }
                    } else {
                        String::new()
                    };
                    let richer = levels[richer as usize]
                        .as_ref()
                        .expect("richer tier was rendered first");
                    let tier = compressed(rendered, richer, &path, level, config.output_format);
                    levels[level as usize] = Some(tier);
                }
            }

            (file_id, FileTiers { levels })
        };

        let files = if config.enable_parallel {
            let files: Vec<_> = index.files.iter().collect();
            let rendered: Vec<_> = files.into_par_iter().map(render_file).collect();
            rendered.into_iter().collect()
        } else {
            index.files.iter().map(render_file).collect()
        };

        Ok(Tiers {
            output_format: config.output_format,
            tokenizer_encoding: config.tokenizer_encoding,
            token_counts_estimated: false,
            files,
        })
    }
}

fn compressed(
    content: String,
    richer: &RenderedTier,
    path: &str,
    level: FidelityLevel,
    format: OutputFormat,
) -> RenderedTier {
    let content = if content.trim().is_empty() || content == *richer.content {
        Arc::clone(&richer.content)
    } else {
        Arc::from(content)
    };

    RenderedTier::new(content, path, level, format)
}
