//! Read, redact, and analyze repository source files.

use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::ops::Range;

use la_arena::ArenaMap;
use leakguard::{Kind, Redactor};
use rayon::prelude::*;
use tree_sitter as ts;

use crate::Config;
use crate::error::Error;
use crate::index::{File, FileId, Index};
use crate::languages::LanguageAnalysis;

/// Byte ranges captured from UTF-8 source after optional redaction, sorted and deduplicated.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Analysis {
    /// Documentation ranges, including language-specific documentation comments.
    pub docstrings: Vec<Range<usize>>,
    /// Import statement ranges retained in outlines.
    pub imports: Vec<Range<usize>>,
    /// Declaration header ranges used by the signatures tier.
    pub sigs: Vec<Range<usize>>,
    /// Additional ranges retained in the documented skeleton tier.
    pub skel: Vec<Range<usize>>,
}

/// UTF-8 source after optional redaction and language-specific outline ranges.
#[derive(Default)]
pub struct Source {
    /// Source bytes. Keep these valid UTF-8 and aligned with captured ranges.
    pub bytes: Vec<u8>,
    /// Outline ranges, or `None` when no language parser was applied.
    pub analysis: Option<Analysis>,
}

/// Source files and shared per-language dependency analysis.
#[derive(Default)]
pub struct Repository {
    /// Readable sources keyed by file IDs from the associated index.
    ///
    /// Oversized, binary, and non-UTF-8 files have no source entry.
    pub sources: ArenaMap<FileId, Source>,
    /// Per-language dependency state keyed by registered language IDs.
    pub analyses: HashMap<&'static str, Box<dyn LanguageAnalysis>>,
}

/// Reads bounded source files and redacts recognized secrets before parsing.
pub struct RepositoryReader {
    redactor: Redactor,
}

impl Default for RepositoryReader {
    fn default() -> Self {
        Self::new()
    }
}

impl RepositoryReader {
    /// Creates a reader with the built-in secret detection rules.
    pub fn new() -> Self {
        Self {
            redactor: Redactor::only(&[
                Kind::AwsAccessKey,
                Kind::AzureConnectionString,
                Kind::DiscordToken,
                Kind::GitHubToken,
                Kind::GoogleApiKey,
                Kind::Jwt,
                Kind::OpenAiKey,
                Kind::PrivateKey,
                Kind::SlackToken,
                Kind::StripeKey,
                Kind::TelegramToken,
                Kind::UrlCredentials,
            ]),
        }
    }

    /// Reads indexed files, skipping oversized, binary, and non-UTF-8 sources.
    ///
    /// # Errors
    ///
    /// Returns an error if a file cannot be read or language analysis fails.
    pub fn read(&self, index: &Index, config: &Config) -> Result<Repository, Error> {
        let limit = config.max_file_size_bytes.get();
        let queries: HashMap<_, _> = index
            .languages
            .iter()
            .map(|(&id, language)| Ok((id, language.query()?)))
            .collect::<Result<_, Error>>()?;

        let analyses: HashMap<_, _> = index
            .languages
            .iter()
            .map(|(&id, language)| (id, language.create_analysis()))
            .collect();

        let read_file = |parser: &mut ts::Parser, (file_id, file): (FileId, &File)| {
            let path = index.root.join(&file.path);
            let mut bytes = Vec::new();
            fs::File::open(&path)
                .and_then(|file| {
                    file.take((limit as u64).saturating_add(1))
                        .read_to_end(&mut bytes)
                })
                .map_err(|source| Error::Io { path, source })?;

            if bytes.len() > limit
                || bytes
                    .iter()
                    .any(|&byte| matches!(byte, 0..=8 | 11 | 14..=31))
            {
                return Ok(None);
            }

            let Ok(text) = std::str::from_utf8(&bytes) else {
                return Ok(None);
            };

            if config.redact_secrets {
                let matches = self.redactor.find(text);

                for matched in matches {
                    for byte in &mut bytes[matched.start..matched.end] {
                        if !matches!(*byte, b'\r' | b'\n') {
                            *byte = b'x';
                        }
                    }
                }
            }

            let analysis = file
                .language
                .map(|id| {
                    index.languages[id].analyze(
                        file_id,
                        parser,
                        &queries[id],
                        &bytes,
                        analyses[id].as_ref(),
                    )
                })
                .transpose()?;

            Ok(Some((file_id, Source { bytes, analysis })))
        };

        let sources = if config.enable_parallel {
            let files: Vec<_> = index.files.iter().collect();
            let results: Vec<_> = files
                .into_par_iter()
                .map_init(ts::Parser::new, read_file)
                .collect::<Result<_, Error>>()?;
            results.into_iter().flatten().collect()
        } else {
            let mut parser = ts::Parser::new();
            index
                .files
                .iter()
                .filter_map(|file| read_file(&mut parser, file).transpose())
                .collect::<Result<_, Error>>()?
        };

        Ok(Repository { sources, analyses })
    }
}
