//! Shared embedded-language outlines and file dependencies for Vue and Svelte.

use std::collections::{HashMap, HashSet};
use std::sync::{LazyLock, Mutex, OnceLock};

use la_arena::ArenaMap;
use tree_sitter as ts;

use super::javascript::dependencies::{Import, ImportKind};
use super::local::{self, text};
use super::{
    Language, LanguageAnalysis, css::Css, javascript::JavaScript, scss::Scss,
    typescript::TypeScript,
};
use crate::error::Error;
use crate::index::{FileId, Index};
use crate::repo::{Analysis, Repository};

static TYPESCRIPT: LazyLock<TypeScript> = LazyLock::new(TypeScript::default);
static TSX: LazyLock<TypeScript> = LazyLock::new(TypeScript::tsx);
static JAVASCRIPT: JavaScript = JavaScript;
static CSS: Css = Css;
static SCSS: Scss = Scss;
static QUERIES: [OnceLock<ts::Query>; 10] = [const { OnceLock::new() }; 10];

fn embedded_query(language: &dyn Language, vue: bool) -> Result<&'static ts::Query, Error> {
    let slot = match language.id() {
        "javascript" => 0,
        "typescript" => 1,
        "tsx" => 2,
        "css" => 3,
        "scss" => 4,
        _ => {
            return Err(Error::InvalidPipeline(
                "unsupported embedded component language",
            ));
        }
    };
    let cache = &QUERIES[slot * 2 + usize::from(vue)];
    if let Some(query) = cache.get() {
        return Ok(query);
    }
    let mut source = language.source_query().to_owned();
    if vue && slot < 3 {
        source.push('\n');
        source.push_str(include_str!("../../queries/vue_script.scm"));
        if slot != 0 {
            source.push('\n');
            source.push_str(include_str!("../../queries/vue_typescript.scm"));
        }
    }
    let query = ts::Query::new(&language.grammar(), &source)?;
    Ok(cache.get_or_init(|| query))
}

pub(super) fn query(language: &dyn Language, vue: bool) -> Result<ts::Query, Error> {
    // Validate embedded queries up front so invalid built-in queries propagate as errors.
    for language in [
        &JAVASCRIPT as &dyn Language,
        &*TYPESCRIPT,
        &*TSX,
        &CSS,
        &SCSS,
    ] {
        embedded_query(language, vue)?;
    }
    Ok(ts::Query::new(
        &language.grammar(),
        language.source_query(),
    )?)
}

fn attribute<'a>(tag: ts::Node<'_>, source: &'a [u8], name: &str) -> Option<&'a str> {
    let mut cursor = tag.walk();
    for attribute in tag
        .named_children(&mut cursor)
        .filter(|node| node.kind() == "attribute")
    {
        let key = attribute.named_child(0)?;
        if key.kind() != "attribute_name" || !text(key, source).eq_ignore_ascii_case(name) {
            continue;
        }
        let Some(value) = attribute.named_child(1) else {
            return Some("");
        };
        let raw = text(value, source);
        return if value.kind() == "quoted_attribute_value" {
            let quote = raw.chars().next()?;
            if !matches!(quote, '\'' | '"') {
                return None;
            }
            raw.strip_prefix(quote)?.strip_suffix(quote)
        } else {
            Some(raw)
        };
    }
    None
}

fn embedded_language(node: ts::Node<'_>, source: &[u8]) -> Option<&'static dyn Language> {
    if node.kind() != "raw_text" {
        return None;
    }
    let parent = node.parent()?;
    let tag = parent.named_child(0)?;
    if attribute(tag, source, "src").is_some() {
        return None;
    }
    let lang = attribute(tag, source, "lang")
        .unwrap_or("")
        .to_ascii_lowercase();
    if parent.kind() == "style_element" {
        if attribute(tag, source, "type").is_some_and(|kind| !kind.eq_ignore_ascii_case("text/css"))
        {
            return None;
        }
        return match lang.as_str() {
            "" | "css" => Some(&CSS),
            "scss" => Some(&SCSS),
            _ => None,
        };
    }
    if parent.kind() != "script_element" {
        return None;
    }
    if attribute(tag, source, "type").is_some_and(|kind| {
        !matches!(
            kind.to_ascii_lowercase().as_str(),
            "" | "module" | "text/javascript" | "application/javascript"
        )
    }) {
        return None;
    }
    match lang.as_str() {
        "" | "js" | "javascript" | "jsx" => Some(&JAVASCRIPT),
        "ts" | "typescript" => Some(&*TYPESCRIPT),
        "tsx" => Some(&*TSX),
        _ => None,
    }
}

pub(super) fn supplement(
    file: FileId,
    root: ts::Node<'_>,
    source: &[u8],
    analysis: &mut Analysis,
    vue: bool,
) {
    let mut parser = ts::Parser::new();
    local::visit(root, |node| {
        let Some(language) = embedded_language(node, source) else {
            return;
        };
        let Ok(query) = embedded_query(language, vue) else {
            return;
        };
        let Ok(inner) = language.analyze(file, &mut parser, query, &source[node.byte_range()], &())
        else {
            return;
        };
        let offset = node.start_byte();
        for (target, ranges) in [
            (&mut analysis.sigs, inner.sigs),
            (&mut analysis.skel, inner.skel),
            (&mut analysis.imports, inner.imports),
            (&mut analysis.docstrings, inner.docstrings),
        ] {
            target.extend(
                ranges
                    .into_iter()
                    .map(|range| range.start + offset..range.end + offset),
            );
        }
    });
}

#[derive(Debug, Default)]
struct ComponentState {
    scripts: ArenaMap<FileId, Vec<Import>>,
    assets: ArenaMap<FileId, Vec<String>>,
    scss: ArenaMap<FileId, local::References>,
    typed: HashSet<FileId>,
}

#[derive(Debug, Default)]
pub(super) struct ComponentAnalysis {
    state: Mutex<ComponentState>,
}

impl LanguageAnalysis for ComponentAnalysis {
    fn extract_dependencies(&self, file: FileId, nodes: &[ts::Node<'_>], source: &[u8]) {
        let mut scripts = Vec::new();
        let mut assets = Vec::new();
        let mut scss = local::References::default();
        let mut typed = false;
        let mut parser = ts::Parser::new();
        for &node in nodes {
            if let Some(language) = embedded_language(node, source) {
                let raw = &source[node.byte_range()];
                if parser.set_language(&language.grammar()).is_err() {
                    continue;
                }
                let Some(tree) = parser.parse(raw, None) else {
                    continue;
                };
                if tree.root_node().has_error() {
                    continue;
                }
                let script = matches!(language.id(), "javascript" | "typescript" | "tsx");
                typed |= matches!(language.id(), "typescript" | "tsx");
                let mut dependencies = Vec::new();
                local::visit(tree.root_node(), |node| {
                    let import = if script {
                        matches!(
                            node.kind(),
                            "import_statement"
                                | "export_statement"
                                | "import_require_clause"
                                | "call_expression"
                        )
                    } else {
                        matches!(
                            node.kind(),
                            "import_statement" | "use_statement" | "forward_statement"
                        ) || node.kind() == "call_expression"
                            && node.named_child(0).is_some_and(|name| {
                                name.kind() == "function_name"
                                    && text(name, raw).eq_ignore_ascii_case("url")
                            })
                    };
                    if import {
                        dependencies.push(node);
                    }
                });
                if script {
                    for node in dependencies {
                        super::javascript::dependencies::extract(node, raw, &mut scripts);
                    }
                } else if language.id() == "scss" {
                    for (kind, path) in super::scss::extract(&dependencies, raw).imports {
                        if kind == "css" {
                            assets.push(path);
                        } else {
                            scss.imports.push((kind, path));
                        }
                    }
                } else {
                    assets.extend(
                        super::css::extract(&dependencies, raw)
                            .imports
                            .into_iter()
                            .map(|(_, path)| path),
                    );
                }
                continue;
            }
            let mut cursor = node.walk();
            let Some(tag) = node
                .named_children(&mut cursor)
                .find(|child| child.kind() == "tag_name")
                .map(|name| text(name, source).to_owned())
            else {
                continue;
            };
            if tag == "script" {
                typed |= attribute(node, source, "lang").is_some_and(|lang| {
                    matches!(
                        lang.to_ascii_lowercase().as_str(),
                        "ts" | "typescript" | "tsx"
                    )
                });
            }
            let mut cursor = node.walk();
            for attr in node
                .named_children(&mut cursor)
                .filter(|node| node.kind() == "attribute")
            {
                let Some(name) = attr
                    .named_child(0)
                    .filter(|node| node.kind() == "attribute_name")
                else {
                    continue;
                };
                let name = text(name, source).to_ascii_lowercase();
                let valid = match name.as_str() {
                    "src" => matches!(
                        tag.as_str(),
                        "script"
                            | "style"
                            | "template"
                            | "img"
                            | "audio"
                            | "video"
                            | "source"
                            | "iframe"
                            | "embed"
                            | "track"
                            | "input"
                    ),
                    "href" => matches!(tag.as_str(), "a" | "area" | "link"),
                    "poster" => tag == "video",
                    "data" => tag == "object",
                    _ => false,
                };
                if !valid {
                    continue;
                }
                let Some(value) = attribute(node, source, &name).filter(|value| {
                    !value.is_empty()
                        && !value.starts_with('/')
                        && !value.contains([':', '&', '{', '}', '\\', '\0'])
                }) else {
                    continue;
                };
                if name == "src" && matches!(tag.as_str(), "script" | "style") {
                    scripts.push(Import {
                        path: value.into(),
                        kind: ImportKind::Module,
                    });
                } else if !value.starts_with('~')
                    && let Some(path) = value
                        .split(['?', '#'])
                        .next()
                        .filter(|path| !path.is_empty())
                {
                    assets.push(path.to_owned());
                }
            }
        }
        let mut state = self.state.lock().unwrap();
        state.scripts.insert(file, scripts);
        state.assets.insert(file, assets);
        state.scss.insert(file, scss);
        if typed {
            state.typed.insert(file);
        } else {
            state.typed.remove(&file);
        }
    }

    fn resolve_dependencies(
        &self,
        index: &Index,
        repository: &Repository,
    ) -> Vec<(FileId, FileId)> {
        let state = self.state.lock().unwrap();
        let mut edges = super::javascript::resolve::resolve_components(
            index,
            repository,
            &state.scripts,
            &state.typed,
        );
        edges.extend(super::scss::resolve(index, repository, &state.scss));
        // Literal assets can be binary and still contribute a path-only dependency.
        let files: HashMap<_, _> = index
            .files
            .iter()
            .map(|(id, file)| (file.path.as_path(), id))
            .collect();
        for (file, assets) in state.assets.iter() {
            let directory = index.files[file].path.parent().unwrap();
            for asset in assets {
                if let Some(target) = local::find(index, &files, &directory.join(asset)) {
                    edges.push((file, target));
                }
            }
        }
        local::finish(edges)
    }
}
