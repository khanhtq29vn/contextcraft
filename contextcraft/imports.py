"""Resolve imports with the implementation for each source file's language."""

from __future__ import annotations

from collections import defaultdict

from contextcraft.models import Import, ImportResolution, Index, Source


class ImportResolver:
    """Resolve imports using the languages detected during indexing."""

    def resolve(self, index: Index, source: Source) -> list[ImportResolution]:
        """Resolve source imports against files in the index.

        Args:
            index: Indexed files and their owning project roots.
            source: Import records extracted from those files.

        Returns:
            Resolutions sorted by import ID. Imports from files with no detected
            language remain unresolved. External packages are neither loaded
            nor imported.

        Raises:
            KeyError: If an import uses a language ID absent from index.languages.
        """
        groups: dict[str, dict[int, Import]] = defaultdict(dict)
        resolutions = []

        for import_id, record in enumerate(source.imports):
            language_id = index.files[record.source_file_id].language_id

            if language_id is None:
                resolutions.append(
                    ImportResolution(
                        import_id=import_id,
                        unresolved_names=(
                            "." * record.relative_level + record.module_name,
                        ),
                    )
                )
                continue

            groups[language_id][import_id] = record

        for language_id, imports in groups.items():
            resolutions.extend(
                index.languages[language_id].resolve_imports(
                    index.files, index.modules, imports
                )
            )

        return sorted(resolutions, key=lambda record: record.import_id)
