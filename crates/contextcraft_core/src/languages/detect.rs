//! Filename, extension, and content-based language detection.

use std::path::Path;

use super::Language;

/// Content evidence used to distinguish languages sharing an extension.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Evidence {
    /// The source does not distinguish this language from other candidates.
    Unknown,
    /// The source contains a distinguishing feature of this language.
    Supports,
    /// The source is incompatible with this language.
    RulesOut,
}

pub(crate) struct LanguageDetector<'a> {
    languages: &'a [Box<dyn Language>],
}

impl<'a> LanguageDetector<'a> {
    pub(crate) fn new(languages: &'a [Box<dyn Language>]) -> Self {
        Self { languages }
    }

    pub(crate) fn detect(
        &self,
        path: &Path,
        source: impl FnOnce() -> Option<Vec<u8>>,
    ) -> Option<&'static str> {
        let name = path.file_name()?.to_str();
        let filenames: Vec<_> = self
            .languages
            .iter()
            .filter(|language| name.is_some_and(|name| language.matches_filename(name)))
            .collect();
        let candidates = if filenames.is_empty() {
            self.languages
                .iter()
                .filter(|language| {
                    language.file_extensions().iter().any(|extension| {
                        path.extension()
                            .is_some_and(|suffix| suffix == extension.trim_start_matches('.'))
                    })
                })
                .collect()
        } else {
            filenames
        };

        if candidates.len() == 1 {
            return Some(candidates[0].id());
        }

        if candidates.is_empty() {
            // Unknown extensions are not scripts merely because they contain a shebang.
            if path.extension().is_some() {
                return None;
            }
            let bytes = source()?;
            let text = std::str::from_utf8(&bytes).ok()?;
            let interpreter = interpreter(text.lines().next()?)?;
            return self
                .languages
                .iter()
                .filter(|language| language.interpreters().contains(&interpreter))
                .map(|language| language.id())
                .min();
        }

        let bytes = source();
        let bytes = bytes
            .as_deref()
            .filter(|bytes| !bytes.contains(&0) && std::str::from_utf8(bytes).is_ok());
        let mut supported = Vec::new();
        let mut unknown = Vec::new();

        for language in candidates {
            match bytes.map_or(Evidence::Unknown, |bytes| language.content_evidence(bytes)) {
                Evidence::Supports => supported.push(language.id()),
                Evidence::Unknown => unknown.push(language.id()),
                Evidence::RulesOut => {}
            }
        }

        if !supported.is_empty() {
            return supported.into_iter().min();
        }

        // C-compatible headers remain C unless there is positive C++ evidence.
        if path.extension().is_some_and(|extension| extension == "h") && unknown.contains(&"c") {
            return Some("c");
        }
        unknown.into_iter().min()
    }
}

fn interpreter(line: &str) -> Option<&str> {
    let mut words = line.strip_prefix("#!")?.split_whitespace();
    let command = Path::new(words.next()?).file_name()?.to_str()?;
    let command = if command == "env" {
        loop {
            let word = words.next()?;
            match word {
                "-S" | "--split-string" | "-i" | "--ignore-environment" | "--" => continue,
                _ if word.starts_with('-') => return None,
                _ if word.contains('=') => continue,
                _ => break word,
            }
        }
    } else {
        command
    };
    Path::new(command).file_name()?.to_str()
}
