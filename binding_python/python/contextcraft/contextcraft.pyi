"""Typed interface to the native ContextCraft extension.

Configuration is mutable. Snapshot properties are read-only, and collection
properties return copies. File and package IDs are local to one analysis.
"""

from os import PathLike
from pathlib import Path
from typing import ClassVar, final

__version__: str
"""Distribution version shared with the Rust workspace."""

@final
class OutputFormat:
    """Native format constants. These are not instances of enum.Enum."""

    MARKDOWN: ClassVar[OutputFormat]
    """Markdown headings and fenced source blocks. The default format."""
    XML: ClassVar[OutputFormat]
    """XML elements with escaped paths and source content."""
    JSON: ClassVar[OutputFormat]
    """JSON path listing and selected file blocks."""

    def as_str(self) -> str:
        """Return ``markdown``, ``xml``, or ``json``."""

@final
class TokenizerEncoding:
    """Native tokenizer vocabulary constants, not enum.Enum members."""

    GPT2: ClassVar[TokenizerEncoding]
    """Original GPT-2 vocabulary, named ``gpt2``."""
    R50K_BASE: ClassVar[TokenizerEncoding]
    """GPT-3 vocabulary, named ``r50k_base``."""
    P50K_BASE: ClassVar[TokenizerEncoding]
    """Codex vocabulary, named ``p50k_base``."""
    P50K_EDIT: ClassVar[TokenizerEncoding]
    """Edit-model vocabulary, named ``p50k_edit``."""
    CL100K_BASE: ClassVar[TokenizerEncoding]
    """Default vocabulary, named ``cl100k_base``."""
    O200K_BASE: ClassVar[TokenizerEncoding]
    """Vocabulary named ``o200k_base``."""
    O200K_HARMONY: ClassVar[TokenizerEncoding]
    """Harmony vocabulary, named ``o200k_harmony``."""

    def as_str(self) -> str:
        """Return the tokenizer identifier, such as ``cl100k_base``."""

@final
class FidelityLevel:
    """Native fidelity constants, usable as dictionary keys."""

    TREE: ClassVar[FidelityLevel]
    """Path-only listing without a source block."""
    SIGS: ClassVar[FidelityLevel]
    """Declaration headers and imports, with richer content as a fallback."""
    SKEL: ClassVar[FidelityLevel]
    """Documented declaration outline, with full source as a fallback."""
    FULL: ClassVar[FidelityLevel]
    """Complete source after optional redaction."""

    def as_str(self) -> str:
        """Return ``TREE``, ``SIGS``, ``SKEL``, or ``FULL``."""

@final
class Config:
    """Mutable settings with the same defaults as the Rust core.

    Assign a new list to change a collection field. In-place edits to a returned
    list do not update the configuration. Zero limits raise ValueError at
    construction or run time. Negative or oversized integers raise OverflowError.
    """

    enable_parallel: bool
    """Use Rayon for loading and rendering. Defaults to True."""
    budget_tokens: int
    """Maximum tokens in the complete artifact. Defaults to 16000."""
    focus_query: str | None
    """Task description used for relevance ranking. Defaults to None."""
    focus_files: list[str]
    """Paths, filenames, directories, or globs to favor. Defaults to an empty list."""
    output_format: OutputFormat
    """Output serialization. Defaults to OutputFormat.MARKDOWN."""
    exclude_patterns: list[str]
    """Repository-relative ignore globs without a leading exclusion marker."""
    respect_gitignore: bool
    """Honor Git exclusion rules. Defaults to True."""
    redact_secrets: bool
    """Redact recognized secrets while preserving byte offsets. Defaults to True."""
    max_file_size_bytes: int
    """Maximum source and manifest size. Defaults to 1048576 bytes."""
    tokenizer_encoding: TokenizerEncoding
    """Token vocabulary. Defaults to TokenizerEncoding.CL100K_BASE."""
    allow_token_estimates: bool
    """Permit estimates in pipeline data. Defaults to True. Current counts are exact."""

    def __init__(
        self,
        *,
        enable_parallel: bool = True,
        budget_tokens: int = 16000,
        focus_query: str | None = None,
        focus_files: list[str] | None = None,
        output_format: OutputFormat = ...,
        exclude_patterns: list[str] | None = None,
        respect_gitignore: bool = True,
        redact_secrets: bool = True,
        max_file_size_bytes: int = 1048576,
        tokenizer_encoding: TokenizerEncoding = ...,
        allow_token_estimates: bool = True,
    ) -> None:
        """Create settings, using independent empty lists when none are supplied."""

@final
class ContextCraft:
    """Run repository compression with mutable settings."""

    config: Config
    """Settings read at the beginning of each run."""

    def __init__(self, config: Config | None = None) -> None:
        """Retain the supplied configuration or create default settings."""

    def run(self, root: str | PathLike[str] = ".") -> RepositoryAnalysis:
        """Analyze a local directory, releasing the GIL during Rust processing.

        Each call rereads the repository and snapshots its configuration before
        starting. Raises OSError for filesystem failures, ValueError for invalid
        settings, manifests, or budgets, and RuntimeError for analysis failures.
        """

@final
class TokenCounter:
    """Exact text token counter backed by the Rust tokenizer."""

    def __init__(
        self, encoding: TokenizerEncoding = ..., allow_estimates: bool = True
    ) -> None:
        """Select a vocabulary. The current implementation never estimates."""

    def count(self, content: str) -> int:
        """Count text tokens, treating special-token markers as ordinary text."""

    def count_full_sources(
        self, tiers: Tiers, enable_parallel: bool = True
    ) -> dict[int, int]:
        """Count FULL-tier source tokens by file ID, releasing the GIL.

        Omit files without a FULL tier. Parallel counting uses the shared Rayon pool.
        """

    def used_estimates(self) -> bool:
        """Return False with the current exact tokenizer."""

@final
class File:
    """Repository-relative file metadata. IDs are local to the containing index.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def path(self) -> Path:
        """File path relative to the repository root."""

    @property
    def package_id(self) -> int:
        """Owning package ID, including the fallback package when needed."""

    @property
    def language(self) -> str | None:
        """Registered language ID, or None for an unsupported extension."""

@final
class PackageDependency:
    """Named dependency on another indexed local package.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def alias(self) -> str:
        """Language-specific dependency name or alias."""

    @property
    def package(self) -> int:
        """Referenced package ID in the same index."""

@final
class Package:
    """Local package metadata shared by language implementations.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def root(self) -> Path:
        """Package directory relative to the repository root."""

    @property
    def name(self) -> str | None:
        """Declared package name, if available."""

    @property
    def language(self) -> str | None:
        """Package language, or None for the fallback package."""

    @property
    def manifests(self) -> list[Path]:
        """Repository-relative manifest paths."""

    @property
    def targets(self) -> list[int]:
        """Indexed target entry file IDs."""

    @property
    def dependencies(self) -> list[PackageDependency]:
        """Explicit local package dependencies."""

@final
class Workspace:
    """Language-specific local workspace membership.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def root(self) -> Path:
        """Workspace directory relative to the repository root."""

    @property
    def language(self) -> str:
        """Language defining the workspace."""

    @property
    def members(self) -> list[int]:
        """Local package IDs belonging to this workspace."""

@final
class Index:
    """Discovered repository files, packages, workspaces, and language IDs.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def root(self) -> Path:
        """Canonical absolute repository directory."""

    @property
    def files(self) -> dict[int, File]:
        """Indexed file metadata keyed by local integer file IDs."""

    @property
    def packages(self) -> dict[int, Package]:
        """Package metadata keyed by local integer package IDs."""

    @property
    def workspaces(self) -> list[Workspace]:
        """Discovered workspace memberships."""

    @property
    def languages(self) -> list[str]:
        """Sorted registered language IDs. Rust trait objects are not exported."""

@final
class Analysis:
    """Outline capture ranges as half-open UTF-8 byte offsets into Source.bytes.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def docstrings(self) -> list[tuple[int, int]]:
        """Documentation comment and docstring ranges."""

    @property
    def imports(self) -> list[tuple[int, int]]:
        """Import statement ranges retained in outlines."""

    @property
    def sigs(self) -> list[tuple[int, int]]:
        """Declaration header ranges used by signatures."""

    @property
    def skel(self) -> list[tuple[int, int]]:
        """Additional documented outline ranges."""

@final
class Source:
    """Readable UTF-8 source after optional secret redaction.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def bytes(self) -> bytes:
        """Immutable source bytes aligned with the captured ranges."""

    @property
    def analysis(self) -> Analysis | None:
        """Captured outline ranges, or None for an unparsed language."""

@final
class Repository:
    """Readable sources from a repository snapshot.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def sources(self) -> dict[int, Source]:
        """Sources keyed by file ID. Skipped sources have no entry."""

@final
class Graph:
    """Directed local file dependencies with importer-to-dependency edges.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def dependencies(self) -> list[tuple[int, int]]:
        """Sorted pairs of importing file ID and dependency file ID."""

@final
class RenderedTier:
    """Rendered source content and its cached or estimated framed token cost.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def content(self) -> str:
        """Source outline, full source, or path for the TREE tier."""

    @property
    def framed_tokens(self) -> int:
        """Framed token cost. Unselected tiers may retain byte-based estimates."""

@final
class FileTiers:
    """Available fidelity levels for one indexed file.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def levels(self) -> dict[FidelityLevel, RenderedTier]:
        """Available rendered tiers keyed by fidelity level."""

@final
class Tiers:
    """Rendered tiers tied to the run's output format and tokenizer vocabulary.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def output_format(self) -> OutputFormat:
        """Serialization format used for framed costs."""

    @property
    def tokenizer_encoding(self) -> TokenizerEncoding:
        """Tokenizer vocabulary used for exact costs."""

    @property
    def token_counts_estimated(self) -> bool:
        """Whether the core reports fallback token estimates."""

    @property
    def files(self) -> dict[int, FileTiers]:
        """Available tier data keyed by file ID."""

@final
class Artifact:
    """Serialized repository context and the final selected fidelity levels.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def content(self) -> str:
        """Complete context including path listings and output framing."""

    @property
    def tokens(self) -> int:
        """Token count of the complete serialized context."""

    @property
    def token_counts_estimated(self) -> bool:
        """Whether any allocation or final token count used a fallback estimate."""

    @property
    def selected_tiers(self) -> dict[int, FidelityLevel]:
        """Final fidelity level for every indexed file."""

@final
class RepositoryAnalysis:
    """Analysis snapshot returned by ContextCraft.run.

    Attributes are read-only. Collection attributes return copies containing
    shared snapshot objects. Integer IDs only identify files or packages here.

    Created by ContextCraft.run(), not constructed directly.
    """

    @property
    def index(self) -> Index:
        """Discovered repository structure and local package metadata."""

    @property
    def repository(self) -> Repository:
        """Loaded and optionally redacted sources."""

    @property
    def graph(self) -> Graph:
        """Directed file dependencies used for ranking."""

    @property
    def scores(self) -> dict[int, float]:
        """Normalized relevance scores keyed by file ID."""

    @property
    def tiers(self) -> Tiers:
        """Rendered source tiers and their cached or estimated costs."""

    @property
    def artifact(self) -> Artifact:
        """Final token-budgeted output."""
