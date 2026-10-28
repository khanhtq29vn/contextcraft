"""Resolve Python imports within indexed project roots."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from contextcraft.models import File, Import, ImportResolution, ModuleRoot


def resolve_imports(
    files: dict[int, File],
    modules: dict[int, ModuleRoot],
    imports: dict[int, Import],
) -> list[ImportResolution]:
    """Resolve Python imports without importing or executing source.

    Args:
        files: Indexed files keyed by file ID.
        modules: Project roots keyed by each file's module ID.
        imports: Import records keyed by their positions in Source.imports.

    Returns:
        Resolutions sorted by import ID. Lookups stay within each source
        file's project root and recognize packages with __init__.py or
        __init__.pyi, but not namespace packages. A .py file takes precedence
        over its matching .pyi stub. Ambiguous files and names that may be
        attributes are kept separate from definite targets.
    """
    python_files = {
        file_id: file for file_id, file in files.items() if file.language_id == "python"
    }

    paths = {(file.module_id, file.path) for file in python_files.values()}
    packages = {
        (file.module_id, file.path.parent)
        for file in python_files.values()
        if file.path.name in {"__init__.py", "__init__.pyi"}
    }

    locations: dict[int, tuple[Path, str]] = {}
    lookup: dict[tuple[int, str], set[int]] = defaultdict(set)

    for file_id, file in python_files.items():
        project = modules[file.module_id].path
        directory = file.path.parent
        parts = []

        while (
            directory.is_relative_to(project)
            and (file.module_id, directory) in packages
        ):
            parts.append(directory.name)
            directory = directory.parent

        if not parts and file.path.parent != project:
            continue

        package = ".".join(reversed(parts))
        locations[file_id] = (directory, package)

        if file.path.suffix not in {".py", ".pyi"}:
            continue

        # A runtime module and its type stub are one target, not an ambiguity.
        if (
            file.path.suffix == ".pyi"
            and (file.module_id, file.path.with_suffix(".py")) in paths
        ):
            continue

        name = (
            package
            if file.path.stem == "__init__"
            else ".".join(part for part in (package, file.path.stem) if part)
        )

        lookup[file.module_id, name].add(file_id)

    def candidates(module_id: int, module_name: str, anchor: Path | None) -> set[int]:
        return {
            target
            for target in lookup.get((module_id, module_name), ())
            if anchor is None or locations[target][0] == anchor
        }

    resolutions = []

    for import_id, record in sorted(imports.items()):
        source = files[record.source_file_id]
        name = record.module_name
        anchor = None

        if record.relative_level:
            location = locations.get(record.source_file_id)
            package_parts = location[1].split(".") if location and location[1] else []

            if record.relative_level > len(package_parts):
                resolutions.append(
                    ImportResolution(
                        import_id=import_id,
                        unresolved_names=("." * record.relative_level + name,),
                    )
                )
                continue

            assert location is not None
            anchor = location[0]
            prefix = package_parts[: len(package_parts) - record.relative_level + 1]
            name = ".".join([*prefix, *([name] if name else [])])

        targets: set[int] = set()
        ambiguous: set[int] = set()
        unresolved: set[str] = set()
        base = candidates(source.module_id, name, anchor)

        if len(base) == 1:
            targets.update(base)
        elif base:
            ambiguous.update(base)
        else:
            unresolved.add(name)

        for imported_name in record.imported_names:
            if imported_name == "*":
                continue

            qualified = f"{name}.{imported_name}" if name else imported_name
            children = candidates(source.module_id, qualified, anchor)

            if len(base) == 1:
                base_file = files[next(iter(base))]

                if base_file.path.stem != "__init__":
                    children = set()
                else:
                    children = {
                        target
                        for target in children
                        if locations[target][0] == locations[next(iter(base))][0]
                    }

            if len(children) == 1 and len(base) == 1:
                targets.update(children)
            elif children:
                ambiguous.update(children)
            else:
                # Without symbol analysis, this may be an attribute, not a submodule.
                unresolved.add(qualified)

        resolutions.append(
            ImportResolution(
                import_id=import_id,
                target_file_ids=tuple(sorted(targets)),
                ambiguous_file_ids=tuple(sorted(ambiguous)),
                unresolved_names=tuple(sorted(unresolved)),
            )
        )

    return resolutions
