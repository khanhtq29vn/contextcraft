---
title: Control scanned files
description: Use exclusions, Git ignore rules, and file-size limits to control repository input.
---

The CLI accepts a local directory. ContextCraft indexes repository files and reads eligible sources before analyzing them.

## Exclude paths

```sh
contextcraft . --exclude docs --exclude 'fixtures/**' --budget 8k -o context.md
```

Exclusions are repository-relative `ignore::overrides` globs without a leading exclusion marker. Repeat `--exclude` for multiple patterns and quote patterns that contain shell wildcards.

## Git ignore rules

Git exclusion rules are respected by default. To disable that behavior:

```sh
contextcraft . --no-gitignore --budget 8k -o context.md
```

Language-specific exclusions still apply. Disabling Git ignore handling does not make every file a readable source.

## Size and readability

The default maximum file size is 1,048,576 bytes. To change it:

```sh
contextcraft . --max-file-size-bytes 2097152 --budget 8k -o context.md
```

The limit must be positive. Oversized, binary, and non-UTF-8 files remain indexed but have no readable source entry.

## Output files

Existing output files are excluded from scanning on repeated runs, including names containing glob metacharacters. The output directory must already exist. Writing to an existing output file may overwrite it.

Secret redaction is enabled by default, but it cannot detect every credential. Review the artifact before sharing it.
