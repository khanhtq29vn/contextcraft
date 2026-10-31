---
title: "contextcraft-ai-core::package"
description: "Shared local package, dependency, and workspace metadata."
editUrl: false
sidebar:
  order: 74
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Shared local package, dependency, and workspace metadata.

## Structs

### <span id="struct.Package"></span><code style="font-size: 0.85em">struct Package</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`

Local package metadata shared by language implementations.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Package directory relative to the repository root. |
| `name` | `Option<String>` | Declared package name, if available from its manifests. |
| `language` | `Option<&'static str>` | Package language ID, or `None` for the fallback package. |
| `manifests` | `Vec<PathBuf>` | Package manifest paths relative to the repository root. |
| `targets` | `Vec<FileId>` | Known target entry files, such as library and executable roots. |
| `dependencies` | `Vec<PackageDependency>` | Dependency scopes and other resolution rules remain with the language. |

### <span id="struct.PackageDependency"></span><code style="font-size: 0.85em">struct PackageDependency</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Clone`, `PartialEq`, `Eq`

Named dependency on another indexed local package.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `alias` | `String` | Name used to refer to the dependency in this language. |
| `package` | `PackageId` | Dependency package ID in the associated index. |

### <span id="struct.Workspace"></span><code style="font-size: 0.85em">struct Workspace</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Local package membership declared by a language-specific workspace.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `root` | `PathBuf` | Workspace directory relative to the repository root. |
| `language` | `&'static str` | Language whose manifest defines this workspace. |
| `members` | `Vec<PackageId>` | Workspace member IDs in the associated index. |

### <span id="struct.PackageResolution"></span><code style="font-size: 0.85em">struct PackageResolution</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`, `Default`

Package updates and workspaces produced by language-specific resolution.

#### Fields

| Name | Type | Description |
|------|------|-------------|
| `packages` | `ArenaMap<PackageId, Package>` | Resolved metadata replacing the corresponding indexed packages. |
| `workspaces` | `Vec<Workspace>` | Discovered workspace definitions. |
