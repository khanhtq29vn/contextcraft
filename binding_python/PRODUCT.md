# ContextCraft browser preview

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers inspecting the context generated from a local repository before using it with an LLM.

## Product Purpose

Make a generated context artifact inspectable: read and export its exact contents, find files, and compare available fidelity tiers.

## Operating Context

The Python CLI starts a loopback-only server for one analysis snapshot. The browser uses a session URL. Stop the server and rerun the command to refresh the analysis.

## Capabilities and Constraints

- Keep inspection and tier comparison; browser configuration editing and regeneration are outside the confirmed scope.
- Preserve copy, download, path search, selected-only filtering, pagination, relevance, and on-demand file content.
- The generated artifact remains unchanged when viewing another tier.
- Highlight.js from jsDelivr provides syntax highlighting in rendered Markdown and the file tier inspector.
- Load the three preview typefaces from Google Fonts without explicit fallback font stacks.
- Bundle the core preview assets with the Python package. Optionally load pinned Marked.js and DOMPurify from jsDelivr for sanitized Markdown rendering; fall back to raw text if either library cannot load.

## Brand Commitments

Match the existing documentation design recorded in `../docs/DESIGN.md`, adapting it to a working playground.

## Evidence on Hand

The existing preview implementation, Python README and API types establish product behavior. Documentation styles and bundled fonts establish the visual reference.

## Product Principles

- Show real analysis data and retain exact exported content.
- Keep file inspection and tier comparison easy to discover.
- Make snapshot limits explicit beside the work.
