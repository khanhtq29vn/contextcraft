"""Discover repository files, project roots, and focus matches."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

import ignore
from ignore.overrides import OverrideBuilder

from contextcraft.config import Config
from contextcraft.languages import BUILTIN_LANGUAGES
from contextcraft.languages.base import Language
from contextcraft.models import File, Index, ModuleRoot


class Indexer:
    """Discover files using the supplied language definitions.

    Args:
        languages: Language classes providing file detection, root markers,
            and default ignore patterns. Defaults to built-in languages.
    """

    @staticmethod
    def _matches_focus_file(path: str, patterns: list[str]) -> bool:
        filename = PurePosixPath(path).name

        for pattern in patterns:
            pattern = pattern.strip().replace("\\", "/")

            while pattern.startswith("./"):
                pattern = pattern[2:]

            pattern = pattern.lstrip("/")

            if not pattern:
                continue

            directory = pattern.rstrip("/")

            if (
                path == pattern
                or filename == pattern
                or fnmatchcase(path, pattern)
                or fnmatchcase(filename, pattern)
                or (directory and path.startswith(directory + "/"))
            ):
                return True

        return False

    def __init__(
        self,
        *,
        languages: tuple[type[Language], ...] = BUILTIN_LANGUAGES,
    ) -> None:
        self.languages = languages

    def index(self, path: str | Path, config: Config) -> Index:
        """Index the files under a directory and detect their languages.

        Args:
            path: Directory to scan, or a file whose parent directory will be scanned.
            config: Ignore rules and focus-file patterns to apply.

        Returns:
            An index with files numbered in path order, each assigned to its
            nearest project root. It also records detected languages and files
            matching the focus patterns. No source content is read.

        Raises:
            OSError: If the path cannot be resolved or the root is not a directory.
            ignore.Error: If the walker or ignore rules cannot be built.
        """
        path = Path(path).resolve(strict=True)
        root = path.parent if path.is_file() else path

        if not root.is_dir():
            raise NotADirectoryError(root)

        overrides = OverrideBuilder(root)

        for language in self.languages:
            for pattern in language.get_ignore_patterns():
                overrides.add(f"!{pattern}")

        for pattern in config.exclude_patterns:
            overrides.add(f"!{pattern}")

        walker = (
            ignore.WalkBuilder(root)
            .require_git(False)
            .git_ignore(config.respect_gitignore)
            .git_global(config.respect_gitignore)
            .git_exclude(config.respect_gitignore)
            .overrides(overrides.build())
            .build()
        )

        files = tuple(
            sorted(entry.path() for entry in walker if entry.path().is_file())
        )

        projects = {root}
        projects.update(
            path.parent
            for path in files
            if any(
                path.name in language.get_root_files() for language in self.languages
            )
        )
        module_ids = {
            path: module_id for module_id, path in enumerate(sorted(projects))
        }

        owners = sorted(projects, key=lambda path: len(path.parts), reverse=True)
        modules = {
            module_id: ModuleRoot(path=path) for path, module_id in module_ids.items()
        }

        indexed_files = {}
        detected_languages = {}
        focus_file_ids = set()

        for file_id, path in enumerate(files):
            project = next(
                project for project in owners if path.is_relative_to(project)
            )

            language = next(
                (
                    language
                    for language in self.languages
                    if path.suffix in language.get_file_extensions()
                    or path.name in language.get_filenames()
                ),
                None,
            )
            language_id = language.get_language_id() if language is not None else None

            if language is not None:
                detected_languages[language.get_language_id()] = language

            indexed_files[file_id] = File(
                path=path,
                module_id=module_ids[project],
                language_id=language_id,
            )

            if self._matches_focus_file(
                path.relative_to(root).as_posix(), config.focus_files
            ):
                focus_file_ids.add(file_id)

        return Index(
            path=root,
            languages=detected_languages,
            modules=modules,
            files=indexed_files,
            focus_file_ids=frozenset(focus_file_ids),
        )
