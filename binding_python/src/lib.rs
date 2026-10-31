//! Python bindings for AST-aware, personalized-PageRank-ranked, token-budgeted
//! codebase compression for LLMs.

use std::collections::HashMap;
use std::num::NonZeroUsize;
use std::path::PathBuf;

use contextcraft_core as core;
use pyo3::exceptions::{
    PyNotADirectoryError, PyOSError, PyRuntimeError, PyTypeError, PyValueError,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use rayon::prelude::*;

macro_rules! python_enum {
    ($(#[$doc:meta])* $name:ident => $core:path { $($(#[$variant_doc:meta])* $variant:ident),+ $(,)? }) => {
        $(#[$doc])*
        #[pyclass(
            module = "contextcraft.contextcraft",
            frozen,
            eq,
            hash,
            from_py_object,
            rename_all = "SCREAMING_SNAKE_CASE"
        )]
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
        pub enum $name { $($(#[$variant_doc])* $variant),+ }

        impl From<$name> for $core {
            fn from(value: $name) -> Self {
                match value { $($name::$variant => Self::$variant),+ }
            }
        }

        impl From<$core> for $name {
            fn from(value: $core) -> Self {
                match value { $(<$core>::$variant => Self::$variant),+ }
            }
        }

        impl<'py> IntoPyObject<'py> for &$name {
            type Target = $name;
            type Output = Bound<'py, $name>;
            type Error = PyErr;

            fn into_pyobject(self, py: Python<'py>) -> PyResult<Self::Output> {
                (*self).into_pyobject(py)
            }
        }

        #[pymethods]
        impl $name {
            /// Returns the identifier used in configuration or serialized output.
            fn as_str(&self) -> &'static str {
                <$core>::from(*self).as_str()
            }
        }
    };
}

python_enum! {
    /// Serialization format for repository context.
    OutputFormat => core::OutputFormat {
        /// Markdown headings and fenced source blocks.
        Markdown,
        /// Escaped XML elements.
        Xml,
        /// JSON path listings and file blocks.
        Json,
    }
}

python_enum! {
    /// Tokenizer vocabulary used to measure the complete output budget.
    TokenizerEncoding => core::TokenizerEncoding {
        /// Original GPT-2 vocabulary.
        Gpt2,
        /// Vocabulary named r50k_base.
        R50kBase,
        /// Vocabulary named p50k_base.
        P50kBase,
        /// Vocabulary named p50k_edit.
        P50kEdit,
        /// Default vocabulary named cl100k_base.
        Cl100kBase,
        /// Vocabulary named o200k_base.
        O200kBase,
        /// Harmony vocabulary named o200k_harmony.
        O200kHarmony,
    }
}

python_enum! {
    /// Source fidelity selected for an indexed file.
    FidelityLevel => core::tiers::FidelityLevel {
        /// Path-only listing.
        Tree,
        /// Declaration signatures and imports.
        Sigs,
        /// Documented source outline.
        Skel,
        /// Complete readable source.
        Full,
    }
}

/// Mutable scanning, ranking, and output settings.
///
/// Numeric limits must be positive. Assign new lists to update collection fields.
/// Reading a collection field returns a copy rather than a live mutable view.
#[pyclass(module = "contextcraft.contextcraft", get_all, set_all, from_py_object)]
#[derive(Clone)]
pub struct Config {
    /// Whether to analyze sources and render tiers in parallel. Defaults to True.
    pub enable_parallel: bool,
    /// Maximum tokens in the complete artifact. Defaults to 16000.
    pub budget_tokens: usize,
    /// Optional task description used to bias relevance scores.
    pub focus_query: Option<String>,
    /// Paths, filenames, directories, or globs to favor, not force into output.
    pub focus_files: Vec<String>,
    /// Serialization format. Defaults to OutputFormat.MARKDOWN.
    pub output_format: OutputFormat,
    /// Repository-relative exclusion globs without an exclusion prefix.
    pub exclude_patterns: Vec<String>,
    /// Whether to honor Git ignore rules. Defaults to True.
    pub respect_gitignore: bool,
    /// Whether to redact recognized secrets before parsing. Defaults to True.
    pub redact_secrets: bool,
    /// Maximum source and manifest size in bytes. Defaults to 1048576.
    pub max_file_size_bytes: usize,
    /// Tokenizer vocabulary. Defaults to TokenizerEncoding.CL100K_BASE.
    pub tokenizer_encoding: TokenizerEncoding,
    /// Whether pipeline estimates are permitted. The current tokenizer is exact.
    pub allow_token_estimates: bool,
}

impl Default for Config {
    fn default() -> Self {
        let config = core::Config::default();
        Self {
            enable_parallel: config.enable_parallel,
            budget_tokens: config.budget_tokens.get(),
            focus_query: config.focus_query,
            focus_files: config.focus_files,
            output_format: config.output_format.into(),
            exclude_patterns: config.exclude_patterns,
            respect_gitignore: config.respect_gitignore,
            redact_secrets: config.redact_secrets,
            max_file_size_bytes: config.max_file_size_bytes.get(),
            tokenizer_encoding: config.tokenizer_encoding.into(),
            allow_token_estimates: config.allow_token_estimates,
        }
    }
}

impl Config {
    fn to_core(&self) -> PyResult<core::Config> {
        Ok(core::Config {
            enable_parallel: self.enable_parallel,
            budget_tokens: NonZeroUsize::new(self.budget_tokens)
                .ok_or_else(|| PyValueError::new_err("budget_tokens must be positive"))?,
            focus_query: self.focus_query.clone(),
            focus_files: self.focus_files.clone(),
            output_format: self.output_format.into(),
            exclude_patterns: self.exclude_patterns.clone(),
            respect_gitignore: self.respect_gitignore,
            redact_secrets: self.redact_secrets,
            max_file_size_bytes: NonZeroUsize::new(self.max_file_size_bytes)
                .ok_or_else(|| PyValueError::new_err("max_file_size_bytes must be positive"))?,
            tokenizer_encoding: self.tokenizer_encoding.into(),
            allow_token_estimates: self.allow_token_estimates,
        })
    }
}

#[pymethods]
impl Config {
    /// Creates settings with the same defaults as the Rust core.
    ///
    /// Raises ValueError if a numeric limit is zero.
    #[new]
    #[pyo3(signature = (**kwargs))]
    fn new(kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mut config = Self::default();

        if let Some(kwargs) = kwargs {
            for (key, value) in kwargs {
                let key: String = key.extract()?;

                match key.as_str() {
                    "enable_parallel" => config.enable_parallel = value.extract()?,
                    "budget_tokens" => config.budget_tokens = value.extract()?,
                    "focus_query" => config.focus_query = value.extract()?,
                    "focus_files" => {
                        config.focus_files =
                            value.extract::<Option<Vec<String>>>()?.unwrap_or_default();
                    }
                    "output_format" => config.output_format = value.extract()?,
                    "exclude_patterns" => {
                        config.exclude_patterns =
                            value.extract::<Option<Vec<String>>>()?.unwrap_or_default();
                    }
                    "respect_gitignore" => config.respect_gitignore = value.extract()?,
                    "redact_secrets" => config.redact_secrets = value.extract()?,
                    "max_file_size_bytes" => config.max_file_size_bytes = value.extract()?,
                    "tokenizer_encoding" => config.tokenizer_encoding = value.extract()?,
                    "allow_token_estimates" => config.allow_token_estimates = value.extract()?,
                    _ => {
                        return Err(PyTypeError::new_err(format!(
                            "unexpected Config argument: {key}"
                        )));
                    }
                }
            }
        }

        config.to_core()?;
        Ok(config)
    }
}

/// Configurable repository compression pipeline.
#[pyclass(module = "contextcraft.contextcraft", get_all, set_all)]
pub struct ContextCraft {
    /// Mutable settings read at the start of each run.
    pub config: Py<Config>,
}

#[pymethods]
impl ContextCraft {
    /// Creates a pipeline, retaining the supplied Config or creating default settings.
    #[new]
    #[pyo3(signature = (config=None))]
    fn new(py: Python<'_>, config: Option<Py<Config>>) -> PyResult<Self> {
        Ok(Self {
            config: match config {
                Some(config) => config,
                None => Py::new(py, Config::default())?,
            },
        })
    }

    /// Analyzes a local directory and returns a snapshot with its budgeted artifact.
    ///
    /// Accepts a string or os.PathLike path. Each run rereads the repository and
    /// releases the GIL during Rust analysis. Settings are copied before analysis.
    ///
    /// Raises OSError for filesystem failures, ValueError for invalid settings,
    /// manifests, or an insufficient budget, and RuntimeError for analysis failures.
    #[pyo3(signature = (root=".".into()))]
    fn run(&self, py: Python<'_>, root: PathBuf) -> PyResult<RepositoryAnalysis> {
        let config = self.config.borrow(py).to_core()?;
        let analysis = py
            .detach(move || core::ContextCraft::new(config).run(root))
            .map_err(python_error)?;
        RepositoryAnalysis::from_core(py, analysis)
    }
}

/// Repository-relative file metadata. IDs are local to the containing index.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct File {
    /// File path relative to the repository root.
    pub path: PathBuf,
    /// Owning package ID, including the fallback package when needed.
    pub package_id: usize,
    /// Registered language ID, or None for an unsupported extension.
    pub language: Option<&'static str>,
}

/// Named dependency on another indexed local package.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct PackageDependency {
    /// Language-specific dependency name or alias.
    pub alias: String,
    /// Referenced package ID in the same index.
    pub package: usize,
}

/// Local package metadata shared by language implementations.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Package {
    /// Package directory relative to the repository root.
    pub root: PathBuf,
    /// Declared package name, if available.
    pub name: Option<String>,
    /// Package language, or None for the fallback package.
    pub language: Option<&'static str>,
    /// Repository-relative manifest paths.
    pub manifests: Vec<PathBuf>,
    /// Indexed target entry file IDs.
    pub targets: Vec<usize>,
    /// Explicit local package dependencies.
    pub dependencies: Vec<Py<PackageDependency>>,
}

/// Language-specific local workspace membership.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Workspace {
    /// Workspace directory relative to the repository root.
    pub root: PathBuf,
    /// Language defining the workspace.
    pub language: &'static str,
    /// Local package IDs belonging to this workspace.
    pub members: Vec<usize>,
}

/// Discovered repository files, packages, workspaces, and language IDs.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Index {
    /// Canonical absolute repository directory.
    pub root: PathBuf,
    /// Indexed file metadata keyed by local integer file IDs.
    pub files: HashMap<usize, Py<File>>,
    /// Package metadata keyed by local integer package IDs.
    pub packages: HashMap<usize, Py<Package>>,
    /// Discovered workspace memberships.
    pub workspaces: Vec<Py<Workspace>>,
    /// Sorted registered language IDs. Rust trait objects are not exported.
    pub languages: Vec<&'static str>,
}

/// Outline capture ranges as half-open UTF-8 byte offsets into Source.bytes.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Analysis {
    /// Documentation comment and docstring ranges.
    pub docstrings: Vec<(usize, usize)>,
    /// Import statement ranges retained in outlines.
    pub imports: Vec<(usize, usize)>,
    /// Declaration header ranges used by signatures.
    pub sigs: Vec<(usize, usize)>,
    /// Additional documented outline ranges.
    pub skel: Vec<(usize, usize)>,
}

/// Readable UTF-8 source after optional secret redaction.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Source {
    /// Immutable source bytes aligned with the captured ranges.
    pub bytes: Py<PyBytes>,
    /// Captured outline ranges, or None for an unparsed language.
    pub analysis: Option<Py<Analysis>>,
}

/// Readable sources from a repository snapshot.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Repository {
    /// Sources keyed by file ID. Skipped sources have no entry.
    pub sources: HashMap<usize, Py<Source>>,
}

/// Directed local file dependencies with importer-to-dependency edges.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Graph {
    /// Sorted pairs of importing file ID and dependency file ID.
    pub dependencies: Vec<(usize, usize)>,
}

/// Rendered source content and its cached or estimated framed token cost.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct RenderedTier {
    /// Source outline, full source, or path for the TREE tier.
    pub content: String,
    /// Framed token cost. Unselected tiers may retain byte-based estimates.
    pub framed_tokens: usize,
}

/// Available fidelity levels for one indexed file.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct FileTiers {
    /// Available rendered tiers keyed by fidelity level.
    pub levels: HashMap<FidelityLevel, Py<RenderedTier>>,
}

/// Rendered tiers tied to the run's output format and tokenizer vocabulary.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Tiers {
    /// Serialization format used for framed costs.
    pub output_format: OutputFormat,
    /// Tokenizer vocabulary used for exact costs.
    pub tokenizer_encoding: TokenizerEncoding,
    /// Whether the core reports fallback token estimates.
    pub token_counts_estimated: bool,
    /// Available tier data keyed by file ID.
    pub files: HashMap<usize, Py<FileTiers>>,
}

/// Serialized repository context and the final selected fidelity levels.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct Artifact {
    /// Complete context including path listings and output framing.
    pub content: String,
    /// Token count of the complete serialized context.
    pub tokens: usize,
    /// Whether any allocation or final token count used a fallback estimate.
    pub token_counts_estimated: bool,
    /// Final fidelity level for every indexed file.
    pub selected_tiers: HashMap<usize, FidelityLevel>,
}

/// Analysis snapshot returned by ContextCraft.run.
///
/// Attributes are read-only. Collection attributes return copies containing
/// shared snapshot objects. Integer IDs only identify files or packages here.
#[pyclass(module = "contextcraft.contextcraft", frozen, get_all)]
pub struct RepositoryAnalysis {
    /// Discovered repository structure and local package metadata.
    pub index: Py<Index>,
    /// Loaded and optionally redacted sources.
    pub repository: Py<Repository>,
    /// Directed file dependencies used for ranking.
    pub graph: Py<Graph>,
    /// Normalized relevance scores keyed by file ID.
    pub scores: HashMap<usize, f64>,
    /// Rendered source tiers and their cached or estimated costs.
    pub tiers: Py<Tiers>,
    /// Final token-budgeted output.
    pub artifact: Py<Artifact>,
}

impl RepositoryAnalysis {
    fn from_core(py: Python<'_>, analysis: core::RepositoryAnalysis) -> PyResult<Self> {
        let core::RepositoryAnalysis {
            index,
            repository,
            graph,
            scores,
            tiers,
            artifact,
        } = analysis;
        let file_id = |id: core::index::FileId| id.into_raw().into_u32() as usize;
        let package_id = |id: core::index::PackageId| id.into_raw().into_u32() as usize;
        let mut edges = Vec::with_capacity(graph.edge_count());

        for (id, _) in index.files.iter() {
            edges.extend(
                graph
                    .neighbors(id)
                    .map(|target| (file_id(id), file_id(target))),
            );
        }
        edges.sort_unstable();

        let files = index
            .files
            .into_iter()
            .map(|(id, file)| {
                Ok((
                    file_id(id),
                    Py::new(
                        py,
                        File {
                            path: file.path,
                            package_id: package_id(file.package_id),
                            language: file.language,
                        },
                    )?,
                ))
            })
            .collect::<PyResult<_>>()?;
        let packages = index
            .packages
            .into_iter()
            .map(|(id, package)| {
                let dependencies = package
                    .dependencies
                    .into_iter()
                    .map(|dependency| {
                        Py::new(
                            py,
                            PackageDependency {
                                alias: dependency.alias,
                                package: package_id(dependency.package),
                            },
                        )
                    })
                    .collect::<PyResult<_>>()?;
                Ok((
                    package_id(id),
                    Py::new(
                        py,
                        Package {
                            root: package.root,
                            name: package.name,
                            language: package.language,
                            manifests: package.manifests,
                            targets: package.targets.into_iter().map(file_id).collect(),
                            dependencies,
                        },
                    )?,
                ))
            })
            .collect::<PyResult<_>>()?;
        let workspaces = index
            .workspaces
            .into_iter()
            .map(|workspace| {
                Py::new(
                    py,
                    Workspace {
                        root: workspace.root,
                        language: workspace.language,
                        members: workspace.members.into_iter().map(package_id).collect(),
                    },
                )
            })
            .collect::<PyResult<_>>()?;
        let mut languages: Vec<_> = index.languages.into_keys().collect();
        languages.sort_unstable();
        let index = Py::new(
            py,
            Index {
                root: index.root,
                files,
                packages,
                workspaces,
                languages,
            },
        )?;

        let sources = repository
            .sources
            .into_iter()
            .map(|(id, source)| {
                let ranges = |ranges: Vec<std::ops::Range<usize>>| {
                    ranges
                        .into_iter()
                        .map(|range| (range.start, range.end))
                        .collect()
                };
                let analysis = source
                    .analysis
                    .map(|analysis| {
                        Py::new(
                            py,
                            Analysis {
                                docstrings: ranges(analysis.docstrings),
                                imports: ranges(analysis.imports),
                                sigs: ranges(analysis.sigs),
                                skel: ranges(analysis.skel),
                            },
                        )
                    })
                    .transpose()?;
                Ok((
                    file_id(id),
                    Py::new(
                        py,
                        Source {
                            bytes: PyBytes::new(py, &source.bytes).unbind(),
                            analysis,
                        },
                    )?,
                ))
            })
            .collect::<PyResult<_>>()?;
        let files = tiers
            .files
            .into_iter()
            .map(|(id, tiers)| {
                let levels = tiers
                    .levels
                    .into_iter()
                    .zip(core::tiers::FidelityLevel::ALL)
                    .filter_map(|(tier, level)| tier.map(|tier| (level, tier)))
                    .map(|(level, tier)| {
                        let framed_tokens = tier.framed_tokens();
                        Ok((
                            level.into(),
                            Py::new(
                                py,
                                RenderedTier {
                                    content: tier.content.to_string(),
                                    framed_tokens,
                                },
                            )?,
                        ))
                    })
                    .collect::<PyResult<_>>()?;
                Ok((file_id(id), Py::new(py, FileTiers { levels })?))
            })
            .collect::<PyResult<_>>()?;

        Ok(Self {
            index,
            repository: Py::new(py, Repository { sources })?,
            graph: Py::new(
                py,
                Graph {
                    dependencies: edges,
                },
            )?,
            scores: scores
                .into_iter()
                .map(|(id, score)| (file_id(id), score))
                .collect(),
            tiers: Py::new(
                py,
                Tiers {
                    output_format: tiers.output_format.into(),
                    tokenizer_encoding: tiers.tokenizer_encoding.into(),
                    token_counts_estimated: tiers.token_counts_estimated,
                    files,
                },
            )?,
            artifact: Py::new(
                py,
                Artifact {
                    content: artifact.content,
                    tokens: artifact.tokens,
                    token_counts_estimated: artifact.token_counts_estimated,
                    selected_tiers: artifact
                        .selected_tiers
                        .into_iter()
                        .map(|(id, level)| (file_id(id), level.into()))
                        .collect(),
                },
            )?,
        })
    }
}

/// Exact text token counter using the Rust tokenizer.
#[pyclass(module = "contextcraft.contextcraft")]
pub struct TokenCounter {
    counter: core::tokens::TokenCounter,
}

#[pymethods]
impl TokenCounter {
    /// Creates a counter. The current implementation does not use estimates.
    #[new]
    #[pyo3(signature = (encoding=TokenizerEncoding::Cl100kBase, allow_estimates=true))]
    fn new(encoding: TokenizerEncoding, allow_estimates: bool) -> PyResult<Self> {
        Ok(Self {
            counter: core::tokens::TokenCounter::new(encoding.into(), allow_estimates)
                .map_err(python_error)?,
        })
    }

    /// Counts special-token markers as ordinary text, releasing the GIL while counting.
    fn count(&self, py: Python<'_>, content: String) -> PyResult<usize> {
        py.detach(|| self.counter.count(&content))
            .map_err(python_error)
    }

    /// Counts FULL-tier source text by file ID without copying content into Python.
    ///
    /// Releases the GIL while counting. Files without a FULL tier are omitted.
    /// With enable_parallel=True, counts files using the shared Rayon thread pool.
    #[pyo3(signature = (tiers, enable_parallel=true))]
    fn count_full_sources(
        &self,
        py: Python<'_>,
        tiers: &Tiers,
        enable_parallel: bool,
    ) -> PyResult<HashMap<usize, usize>> {
        let count = |(&file, tiers): (&usize, &Py<FileTiers>)| {
            tiers.get().levels.get(&FidelityLevel::Full).map(|tier| {
                self.counter
                    .count(&tier.get().content)
                    .map(|tokens| (file, tokens))
            })
        };

        py.detach(|| -> Result<HashMap<usize, usize>, core::error::Error> {
            if enable_parallel {
                tiers.files.par_iter().filter_map(count).collect()
            } else {
                tiers.files.iter().filter_map(count).collect()
            }
        })
        .map_err(python_error)
    }

    /// Returns False because the current tokenizer always counts exactly.
    fn used_estimates(&self) -> bool {
        self.counter.used_estimates()
    }
}

fn python_error(error: core::error::Error) -> PyErr {
    match error {
        core::error::Error::Io { path, source } => PyOSError::new_err((
            source.raw_os_error().unwrap_or(0),
            source.to_string(),
            path.to_string_lossy().into_owned(),
        )),
        core::error::Error::NotADirectory(path) => {
            PyNotADirectoryError::new_err(format!("not a directory: {}", path.display()))
        }
        error @ (core::error::Error::Manifest { .. }
        | core::error::Error::BudgetTooSmall { .. }
        | core::error::Error::InvalidPipeline(_)) => PyValueError::new_err(error.to_string()),
        error => PyRuntimeError::new_err(error.to_string()),
    }
}

/// Native repository compression, analysis snapshots, and token counting.
#[pymodule]
fn contextcraft(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    module.add_class::<OutputFormat>()?;
    module.add_class::<TokenizerEncoding>()?;
    module.add_class::<FidelityLevel>()?;
    module.add_class::<Config>()?;
    module.add_class::<ContextCraft>()?;
    module.add_class::<File>()?;
    module.add_class::<PackageDependency>()?;
    module.add_class::<Package>()?;
    module.add_class::<Workspace>()?;
    module.add_class::<Index>()?;
    module.add_class::<Analysis>()?;
    module.add_class::<Source>()?;
    module.add_class::<Repository>()?;
    module.add_class::<Graph>()?;
    module.add_class::<RenderedTier>()?;
    module.add_class::<FileTiers>()?;
    module.add_class::<Tiers>()?;
    module.add_class::<Artifact>()?;
    module.add_class::<RepositoryAnalysis>()?;
    module.add_class::<TokenCounter>()?;
    Ok(())
}
