---
title: "contextcraft-ai-core::languages::csharp"
description: "C# outlines, .NET project references, and solution membership."
editUrl: false
sidebar:
  order: 20
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

C# outlines, .NET project references, and solution membership.

Reads `.csproj`, `.sln`, and `.slnx` files, including static Compile membership.
Local namespace/type imports are restricted to visible projects. Build conditions
contribute possible dependencies; MSBuild property expressions, imported build
logic, generated code, and compiler-level type binding are not evaluated.

## Structs

### <span id="struct.CSharp"></span><code style="font-size: 0.85em">struct CSharp</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

CSharp grammar and local project analysis.
