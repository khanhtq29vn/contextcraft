from __future__ import annotations

from pathlib import Path

from contextcraft.languages.base import Language


class LanguageRegistry:
    """Register language metadata and resolve paths to ordered parser candidates.

    Multiple languages may share an extension or filename. Registration order
    determines parser preference; duplicate IDs and aliases are rejected.
    """

    def __init__(self) -> None:
        self._languages: dict[str, type[Language]] = {}
        self._extensions: dict[str, list[type[Language]]] = {}
        self._filenames: dict[str, list[type[Language]]] = {}
        self._aliases: dict[str, type[Language]] = {}

    @property
    def languages(self) -> tuple[type[Language], ...]:
        return tuple(self._languages.values())

    @property
    def ignore_patterns(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                pattern for language in self.languages for pattern in language.spec.ignore_patterns
            )
        )

    def register(self, language: type[Language]) -> None:
        spec = language.spec
        names = (spec.id, *spec.aliases)
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate language alias: {spec.id}")
        for name in names:
            if name in self._languages or name in self._aliases:
                raise ValueError(f"Duplicate language: {name}")

        self._languages[spec.id] = language
        for alias in spec.aliases:
            self._aliases[alias] = language

        for extension in sorted({extension.lower() for extension in spec.extensions}):
            self._extensions.setdefault(extension, []).append(language)

        for filename in spec.filenames:
            self._filenames.setdefault(filename, []).append(language)

    def get(self, language_id: str) -> type[Language] | None:
        return self._languages.get(language_id) or self._aliases.get(language_id)

    def detect_candidates(self, path: str) -> list[type[Language]]:
        """Prefer exact filenames over case-insensitive extensions; return a new list."""
        file_path = Path(path)
        filename = file_path.name

        if filename in self._filenames:
            return list(self._filenames[filename])

        return list(self._extensions.get(file_path.suffix.lower(), []))
