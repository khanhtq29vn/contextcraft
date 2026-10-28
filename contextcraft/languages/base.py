"""Define the contract for language detection, analysis, and tier rendering."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contextcraft.models import File, Import, ImportResolution, ModuleRoot


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
    def extract_docstrings(source: bytes) -> tuple[str, ...]:
        """Return docstring text extracted from UTF-8 source bytes."""
        ...

    @staticmethod
    @abstractmethod
    def extract_imports(source: bytes, file_id: int) -> list[Import]:
        """Extract imports from source and associate each one with file_id."""
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
    @abstractmethod
    def render_sigs(input: bytes) -> str:
        """Return a declaration outline from UTF-8 source bytes."""
        ...

    @staticmethod
    @abstractmethod
    def render_skel(source: bytes) -> str:
        """Return an outline with declarations and retained documentation."""
        ...
