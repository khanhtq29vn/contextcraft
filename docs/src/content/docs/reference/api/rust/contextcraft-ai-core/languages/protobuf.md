---
title: "contextcraft-ai-core::languages::protobuf"
description: "Protocol Buffers schema outlines and repository-root-relative imports."
editUrl: false
sidebar:
  order: 48
  hidden: true
---

<span class="plissken-badge plissken-badge-source" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-orange-low); color: var(--sl-color-orange-high);">Rust</span>

Protocol Buffers schema outlines and repository-root-relative imports.

Supports proto2/proto3 and editions, retaining wire types, tag numbers, reserved
ranges, and streaming RPC signatures. Public/weak imports use the repository
root by default, or literal Buf module roots. Other compiler include paths are unknown.

## Structs

### <span id="struct.Protobuf"></span><code style="font-size: 0.85em">struct Protobuf</code>

<span class="plissken-badge plissken-badge-visibility" style="display: inline-block; padding: 0.05em 0.6em; font-family: var(--sl-font-mono); font-size: var(--sl-text-xs); line-height: 1.6; border-radius: var(--radius-pill, 1rem); vertical-align: middle; background: var(--sl-color-green-low); color: var(--sl-color-green-high);">pub</span>

**Derives:** `Debug`

Protobuf structural outlines and static local imports.
