---
title: Focus on a task
description: Favor relevant files using a task query and focus paths.
---

A task query and focus paths influence file ranking before detail is allocated. They are relevance hints, not inclusion guarantees.

## Describe the task

```sh
contextcraft . --budget 8k --focus "authentication session expiry" -o context.md
```

Use terms that occur in the code or describe the subsystem you are working on. Inspect the artifact to see whether the resulting selection supports your task.

## Favor paths

```sh
contextcraft . --focus-file src/auth --focus-file '*.rs' --budget 12k -o context.md
```

Repeat `--focus-file` to supply paths, filenames, directories, or globs. Quote glob patterns so the shell passes them to ContextCraft unchanged.

## Reduce the scope separately

Focus changes how files are ranked. To leave a directory out of the scan entirely, use `--exclude`:

```sh
contextcraft . --focus "dependency resolution" --exclude docs --budget 8k -o context.md
```

See [control scanned files](../files/) for exclusions and unreadable files. For the ranking equations, read [mathematics and algorithms](../../reference/architecture/).
