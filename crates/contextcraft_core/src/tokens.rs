//! Count ordinary text tokens with the configured tokenizer vocabulary.

use tiktoken::CoreBpe;

use crate::TokenizerEncoding;
use crate::error::Error;

/// Exact token counter backed by a shared tokenizer vocabulary.
pub struct TokenCounter {
    encoder: &'static CoreBpe,
}

impl TokenCounter {
    /// Creates a counter for the selected vocabulary.
    ///
    /// `allow_estimates` is reserved for fallback counting. This implementation
    /// always uses exact counts.
    ///
    /// # Errors
    ///
    /// Returns an error if the vocabulary is unavailable.
    pub fn new(encoding: TokenizerEncoding, _allow_estimates: bool) -> Result<Self, Error> {
        let encoder =
            tiktoken::get_encoding(encoding.as_str()).ok_or_else(|| Error::Tokenization {
                encoding: encoding.as_str(),
                message: "encoding is not available".into(),
            })?;

        Ok(Self { encoder })
    }

    /// Returns the token count, treating special-token markers as ordinary text.
    ///
    /// # Errors
    ///
    /// This implementation always succeeds once the vocabulary is loaded.
    pub fn count(&self, content: &str) -> Result<usize, Error> {
        Ok(self.encoder.count(content))
    }

    /// Returns whether fallback estimates were used. Currently always `false`.
    pub fn used_estimates(&self) -> bool {
        false
    }
}
