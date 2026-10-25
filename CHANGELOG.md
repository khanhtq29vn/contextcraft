# Changelog

## [0.3.2](https://github.com/khanhtq29vn/contextcraft/compare/v0.3.1...v0.3.2) (2026-10-24)


### Bug Fixes

* stop secret-sanitizer leaks and --focus-file substring matches ([#29](https://github.com/khanhtq29vn/contextcraft/issues/29)) ([e30b011](https://github.com/khanhtq29vn/contextcraft/commit/e30b011eef88d911492146327c01d1f83a96aef5))

## [0.3.1](https://github.com/khanhtq29vn/contextcraft/compare/v0.3.0...v0.3.1) (2026-10-23)


### Bug Fixes

* dispatch PyPI publishing as an independent workflow ([dc54054](https://github.com/khanhtq29vn/contextcraft/commit/dc54054cf4c798b9432d6e31c449faf068022640))

## [0.3.0](https://github.com/khanhtq29vn/contextcraft/compare/v0.2.0...v0.3.0) (2026-10-23)


### Features

* add Elixir and Zig support and refine Java summaries ([0934053](https://github.com/khanhtq29vn/contextcraft/commit/093405340760f7527ea320945922fced8b50d747))
* **cli:** expose --encoding flag and sync release-please lockfile config ([6798366](https://github.com/khanhtq29vn/contextcraft/commit/6798366764f2ce37b8f0b50529ce77bc559576fc)), closes [#5](https://github.com/khanhtq29vn/contextcraft/issues/5)
* rewrite language pipeline and expand language support ([#19](https://github.com/khanhtq29vn/contextcraft/issues/19)) ([67ea63b](https://github.com/khanhtq29vn/contextcraft/commit/67ea63be94607373d2587548f60d45bbad6cc524))
* **web:** simplify playground UI ([#24](https://github.com/khanhtq29vn/contextcraft/issues/24)) ([d9ea8b3](https://github.com/khanhtq29vn/contextcraft/commit/d9ea8b31dc6d0c48004915eda6fa4def97ee9b29))


### Bug Fixes

* improve BM25 ranking and token-budget allocation ([#23](https://github.com/khanhtq29vn/contextcraft/issues/23)) ([df5cc05](https://github.com/khanhtq29vn/contextcraft/commit/df5cc055a92f0d2e1a14e0718c385bd89e7f332d))
* make reusable analysis test newline-independent ([1a2ec11](https://github.com/khanhtq29vn/contextcraft/commit/1a2ec11c2aa6d1ca7a8bafe8af5f5dbb73d2ca11))
* remove recursive Helix symlink ([bf99e8d](https://github.com/khanhtq29vn/contextcraft/commit/bf99e8df2be60e82e4c2f6ec52b1e457927c42b3))
* **tests,docs:** strip ANSI codes in CLI help test on GitHub Actions and restore full docs ([7dda840](https://github.com/khanhtq29vn/contextcraft/commit/7dda840d4c38e742d4b2d43689eb43c5e2fa01e9))
* tighten secret redaction placeholder exemptions ([901d028](https://github.com/khanhtq29vn/contextcraft/commit/901d028fc435530a43b7f4e1e9ecac5fee40bc5a))
* use Jinja extension for web template ([ce786dc](https://github.com/khanhtq29vn/contextcraft/commit/ce786dcded4dde72751cf5e842aec03dc651595e))


### Performance Improvements

* speed up budget allocation and reuse repository analysis ([b1113b7](https://github.com/khanhtq29vn/contextcraft/commit/b1113b7ac1da9b215d9bf464376341527937410a))


### Documentation

* add Python API reference ([3aca165](https://github.com/khanhtq29vn/contextcraft/commit/3aca16536a76657e7c4bf72089e927173ccffde7))
* **benchmark,readme:** sync v0.3.0 empirical telemetry, enterprise best practices, and architecture docs ([8c7c2f9](https://github.com/khanhtq29vn/contextcraft/commit/8c7c2f921f389c0e1810249290520d629e4504c0))
* remove implementation filenames from architecture ([3ad8494](https://github.com/khanhtq29vn/contextcraft/commit/3ad849463383ffa0a5050d7de42c0e566c435d0f))

## [0.2.0](https://github.com/khanhtq29vn/contextcraft/compare/v0.1.0...v0.2.0) (2026-10-22)

### ⚠ BREAKING CHANGES

- **ast:** remove SymbolKind; symbol kinds are now strings.

### Bug Fixes

- **metadata:** correct project repository and documentation URLs ([224d77d](https://github.com/khanhtq29vn/contextcraft/commit/224d77da95f7899f85218392c10384189a7c6ee6))
- **types:** remove mypy suppressions and type dependency graphs ([658cd54](https://github.com/khanhtq29vn/contextcraft/commit/658cd543826cec63c3bdc4e455b35dc550a77ee3))

### Documentation

- correct GitHub source repository URL ([f99889e](https://github.com/khanhtq29vn/contextcraft/commit/f99889ea9bea33639f3a3a14505ab7e989174e20))
- migrate to Sphinx with Furo and KaTeX ([e6d7482](https://github.com/khanhtq29vn/contextcraft/commit/e6d748265db10e8481ed1eef72107e3c7c4e575d))

### Code Refactoring

- **ast:** introduce language-specific extractors ([bd188a1](https://github.com/khanhtq29vn/contextcraft/commit/bd188a1f713e17a593fb3ffbed7c32765f36e21a))
