"""Define records exchanged between repository pipeline stages."""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from contextcraft.config import OutputFormat, TokenizerEncoding

if TYPE_CHECKING:
    from contextcraft.languages.base import Language

SEMANTIC_UTILITIES = (0.0, 0.45, 0.82, 1.0)


class FidelityLevel(IntEnum):
    """Order file representations from path-only to full source."""

    TREE = 0
    SIGS = 1
    SKEL = 2
    FULL = 3

    @property
    def semantic_utility(self) -> float:
        """Return the relative utility used to score tier upgrades."""
        return SEMANTIC_UTILITIES[self]


class RenderedTier(msgspec.Struct, frozen=True, kw_only=True):
    """Store rendered content with content-only and framed token counts.

    Framed tokens include format-specific file headers, escaping, and separators,
    using the format and encoding recorded in Tiers. TREE has zero framed cost.
    """

    content: str
    tokens: int
    framed_tokens: int


class Artifact(msgspec.Struct, frozen=True, kw_only=True):
    """Store the final output, token count, and selected file tiers.

    The selected_tiers mapping includes any budget adjustments made by the
    formatter. If token_counts_estimated is true, tokens is only an estimate.
    """

    content: str
    tokens: int
    token_counts_estimated: bool = False
    selected_tiers: dict[int, FidelityLevel] = msgspec.field(default_factory=dict)


class ModuleRoot(msgspec.Struct, frozen=True, kw_only=True):
    """Identify a project root used to group files for import resolution."""

    path: Path


class File(msgspec.Struct, frozen=True, kw_only=True):
    """Record an absolute file path, owning module ID, and detected language."""

    path: Path
    module_id: int
    language_id: str | None = None


class Import(msgspec.Struct, frozen=True, kw_only=True):
    """Describe an import found in a source file.

    Use source_file_id to look up the importing file in Index.files.
    The relative_level counts leading dots, and imported_names holds the names
    requested by a from-import, including '*' for a wildcard.
    """

    source_file_id: int
    module_name: str
    relative_level: int = 0
    imported_names: tuple[str, ...] = ()


class FileAnalysis(msgspec.Struct, frozen=True, kw_only=True):
    """Store extracted metadata and outline spans from one source file.

    Each SIGS or SKEL span is (start_byte, end_byte, indentation), in source
    order. Offsets refer to the analyzed UTF-8 bytes, after any redaction.
    No parse trees, nodes, or rendered text are retained.
    """

    docstrings: tuple[str, ...]
    imports: tuple[Import, ...]
    sigs: tuple[tuple[int, int, int], ...]
    skel: tuple[tuple[int, int, int], ...]


class ImportResolution(msgspec.Struct, frozen=True, kw_only=True):
    """Record targets, ambiguities, and unresolved names for one import.

    The import_id is the record's position in Source.imports. Both target
    and ambiguous file IDs refer to Index.files. An unresolved name may be
    an external dependency or an attribute that requires symbol analysis.
    """

    import_id: int
    target_file_ids: tuple[int, ...] = ()
    ambiguous_file_ids: tuple[int, ...] = ()
    unresolved_names: tuple[str, ...] = ()


class Index(msgspec.Struct, frozen=True, kw_only=True):
    """Store the repository root, project roots, files, and focus matches.

    Module and file IDs belong to this index, and all paths are absolute.
    The focus_file_ids set contains files matched by the focus patterns.
    The languages mapping connects detected language IDs to implementations
    for later stages; it omits languages with no matching files.
    """

    path: Path
    languages: dict[str, type[Language]] = msgspec.field(default_factory=dict)
    modules: dict[int, ModuleRoot] = msgspec.field(default_factory=dict)
    files: dict[int, File] = msgspec.field(default_factory=dict)
    focus_file_ids: frozenset[int] = frozenset()


class Source(msgspec.Struct, frozen=True, kw_only=True):
    """Store loaded UTF-8 source bytes, docstrings, and import records.

    Content and docstrings are keyed by file ID. Files skipped by the loader
    have no content entry. Source bytes are already redacted when that option
    is enabled. Analyses hold metadata and outline spans by file ID for every
    loaded file with a detected language. Renderers use these spans without
    parsing again or caching rendered text.
    """

    content: dict[int, bytes] = msgspec.field(default_factory=dict)
    docstrings: dict[int, tuple[str, ...]] = msgspec.field(default_factory=dict)
    imports: tuple[Import, ...] = ()
    analyses: dict[int, FileAnalysis] = msgspec.field(default_factory=dict)


class Tiers(msgspec.Struct, frozen=True, kw_only=True):
    """Store available fidelity tiers by file ID.

    Every file has a TREE tier, but only files with loaded source have higher
    tiers. The token_counts_estimated flag is true if any count used an estimate.
    Allocation and formatting must use the recorded output format and encoding,
    and the same index, because framed costs depend on paths as well as content.
    """

    output_format: OutputFormat
    tokenizer_encoding: TokenizerEncoding
    files: dict[int, dict[FidelityLevel, RenderedTier]] = msgspec.field(
        default_factory=dict
    )
    token_counts_estimated: bool = False


class Selection(msgspec.Struct, frozen=True, kw_only=True):
    """Record the allocated tier for each file and whether token counts were estimated."""

    tiers: dict[int, FidelityLevel] = msgspec.field(default_factory=dict)
    token_counts_estimated: bool = False
