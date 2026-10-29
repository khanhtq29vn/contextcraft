"""Define the contract for language detection, analysis, and tier rendering."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contextcraft.models import File, FileAnalysis, Import, ImportResolution, ModuleRoot


def _render_spans(source: bytes, spans: tuple[tuple[int, int, int], ...]) -> str:
    parts = [b" " * column + source[start:end] for start, end, column in spans]

    return b"\n".join(parts).decode("utf-8")


class Language(ABC):
    """Define language metadata and source-analysis operations.

    Implementations accept UTF-8 source bytes and use file, module, and
    import IDs from the same analysis. Rendered outlines do not need to be
    executable source.
    """

    @staticmethod
    @abstractmethod
    def get_language_id() -> str:
        """Return the stable language ID stored on indexed files."""
        ...

    @staticmethod
    @abstractmethod
    def get_file_extensions() -> frozenset[str]:
        """Return recognized suffixes, including the leading dot."""
        ...

    @staticmethod
    @abstractmethod
    def get_filenames() -> frozenset[str]:
        """Return exact filenames to recognize regardless of suffix."""
        ...

    @staticmethod
    @abstractmethod
    def get_root_files() -> frozenset[str]:
        """Return filenames that mark a project root for file ownership."""
        ...

    @staticmethod
    @abstractmethod
    def get_package_files() -> frozenset[str]:
        """Return filenames associated with package metadata and dependencies."""
        ...

    @staticmethod
    @abstractmethod
    def get_ignore_patterns() -> tuple[str, ...]:
        """Return default exclusion globs for repository indexing."""
        ...

    @staticmethod
    @abstractmethod
    def analyze(source: bytes, file_id: int) -> FileAnalysis:
        """Extract metadata and outline spans once from UTF-8 source bytes.

        Return sorted, deduplicated spans for later rendering against the same
        bytes. Associate imports with file_id. Do not retain parse trees or nodes.
        """
        ...

    @staticmethod
    @abstractmethod
    def resolve_imports(
        files: dict[int, File],
        modules: dict[int, ModuleRoot],
        imports: dict[int, Import],
    ) -> list[ImportResolution]:
        """Resolve import IDs against indexed files and their project roots.

        Return one resolution per import. Keep unresolved names and ambiguous
        candidates separate from definite targets.
        """
        ...

    @staticmethod
    def render_sigs(source: bytes, analysis: FileAnalysis) -> str:
        """Render declaration spans against their analyzed bytes without parsing."""
        return _render_spans(source, analysis.sigs)

    @staticmethod
    def render_skel(source: bytes, analysis: FileAnalysis) -> str:
        """Render skeleton spans against their analyzed bytes without parsing."""
        return _render_spans(source, analysis.skel)
