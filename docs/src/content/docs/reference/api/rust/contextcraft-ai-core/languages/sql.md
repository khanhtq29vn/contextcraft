---
title: "contextcraft-ai-core::languages::sql"
description: "PostgreSQL 18 schema and routine outlines using tree-sitter-postgres."
editUrl: false
sidebar:
  order: 63
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

PostgreSQL 18 schema and routine outlines using tree-sitter-postgres.

Retains schema names, column types, constraints, view definitions, and function
signatures for the grammar's supported DDL subset. Routine bodies and bulk DML
values are omitted from compact tiers. Unsupported or malformed syntax gets an
outline placeholder rather than recovery fragments; FULL preserves all source.
No database execution, dialect guessing, or cross-file schema binding is performed.

## Structs

### <span id="struct.Sql"></span><code style="font-size: 0.85em">struct Sql</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Sql structural outlines.
