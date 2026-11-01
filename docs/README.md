# ContextCraft docs

Documentation site built with Astro and Starlight.

Run from the repository root:

```sh
pnpm install
just dev-docs
```

- `just build-docs` builds the site into `docs/dist/`.
- `just gen-docs` regenerates the API reference using Plissken.

Edit documentation pages in `docs/src/content/docs/`. Files under `reference/api/` are generated; update their source code instead.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup.
