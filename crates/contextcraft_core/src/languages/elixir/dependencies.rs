//! Literal Elixir module declarations, lexical aliases, and remote module references.

use std::collections::HashMap;

use tree_sitter as ts;

use crate::languages::local::{References, text};

fn arguments(node: ts::Node<'_>) -> Option<ts::Node<'_>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor)
        .find(|node| node.kind() == "arguments")
}

fn target<'a>(node: ts::Node<'_>, source: &'a [u8]) -> &'a str {
    node.child_by_field_name("target")
        .filter(|node| node.kind() == "identifier")
        .map_or("", |node| text(node, source))
}

fn option<'tree>(node: ts::Node<'tree>, source: &[u8], name: &str) -> Option<ts::Node<'tree>> {
    let args = arguments(node)?;
    let mut cursor = args.walk();
    for keywords in args
        .named_children(&mut cursor)
        .filter(|node| node.kind() == "keywords")
    {
        let mut cursor = keywords.walk();
        for pair in keywords.named_children(&mut cursor) {
            if pair
                .child_by_field_name("key")
                .is_some_and(|key| text(key, source).trim().trim_end_matches(':') == name)
            {
                return pair.child_by_field_name("value");
            }
        }
    }
    None
}

#[derive(Clone)]
struct Scope {
    // None denotes a module name produced by code we cannot statically resolve.
    module: Option<String>,
    aliases: HashMap<String, String>,
}

fn module(node: ts::Node<'_>, source: &[u8], scope: &Scope) -> Option<String> {
    match node.kind() {
        "alias" => {
            let name = text(node, source);
            if let Some(name) = name.strip_prefix("Elixir.") {
                return Some(name.into());
            }
            let (first, rest) = name
                .split_once('.')
                .map_or((name, ""), |(first, rest)| (first, rest));
            Some(scope.aliases.get(first).map_or_else(
                || name.to_owned(),
                |prefix| {
                    if rest.is_empty() {
                        prefix.clone()
                    } else {
                        format!("{prefix}.{rest}")
                    }
                },
            ))
        }
        "identifier" if text(node, source) == "__MODULE__" => scope
            .module
            .as_ref()
            .filter(|name| !name.is_empty())
            .cloned(),
        "dot" => {
            let left = module(node.child_by_field_name("left")?, source, scope)?;
            let right = node
                .child_by_field_name("right")
                .filter(|node| node.kind() == "alias")?;
            Some(format!("{left}.{}", text(right, source)))
        }
        _ => None,
    }
}

fn modules(node: ts::Node<'_>, source: &[u8], scope: &Scope) -> Vec<String> {
    if node.kind() == "dot"
        && let Some(tuple) = node
            .child_by_field_name("right")
            .filter(|node| node.kind() == "tuple")
        && let Some(prefix) = node
            .child_by_field_name("left")
            .and_then(|node| module(node, source, scope))
    {
        let mut cursor = tuple.walk();
        return tuple
            .named_children(&mut cursor)
            .filter(|node| node.kind() == "alias")
            .map(|node| format!("{prefix}.{}", text(node, source)))
            .collect();
    }
    module(node, source, scope).into_iter().collect()
}

enum Step<'tree> {
    Enter(ts::Node<'tree>),
    Restore(Scope),
}

pub(super) fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let Some(&first) = nodes.first() else {
        return references;
    };
    let mut root = first;
    while let Some(parent) = root.parent() {
        root = parent;
    }
    let mut scope = Scope {
        module: Some(String::new()),
        aliases: HashMap::new(),
    };
    let mut pending = vec![Step::Enter(root)];
    while let Some(step) = pending.pop() {
        let node = match step {
            Step::Enter(node) => node,
            Step::Restore(previous) => {
                scope = previous;
                continue;
            }
        };
        let kind = target(node, source);
        if node.is_error() || kind == "quote" {
            continue;
        }
        let first = arguments(node).and_then(|args| args.named_child(0));
        let mut nested = None;
        if matches!(kind, "defmodule" | "defprotocol") {
            let name = first.and_then(|first| {
                let current = scope.module.as_ref()?;
                let name = module(first, source, &scope)?;
                let raw = text(first, source);
                let explicit = raw.starts_with("Elixir.")
                    || raw.starts_with("__MODULE__")
                    || scope
                        .aliases
                        .contains_key(raw.split('.').next().unwrap_or(""));
                Some(if current.is_empty() || explicit {
                    name
                } else {
                    format!("{current}.{name}")
                })
            });
            if let Some(name) = &name {
                references.exports.push(name.clone());
                scope
                    .aliases
                    .insert(name.rsplit('.').next().unwrap().to_owned(), name.clone());
            }
            let mut next = scope.clone();
            next.module = name;
            nested = Some(next);
        } else if matches!(kind, "alias" | "import" | "require" | "use" | "defimpl") {
            if let Some(first) = first {
                let names = modules(first, source, &scope);
                references
                    .imports
                    .extend(names.iter().cloned().map(|name| ("module".into(), name)));
                let renamed = option(node, source, "as");
                if kind == "alias" || kind == "require" && renamed.is_some() {
                    for name in names {
                        let alias = match renamed {
                            Some(value) if value.kind() == "alias" => {
                                text(value, source).to_owned()
                            }
                            Some(_) => continue,
                            None => name.rsplit('.').next().unwrap().to_owned(),
                        };
                        scope.aliases.insert(alias, name);
                    }
                }
            }
            if kind == "defimpl" {
                if let Some(value) = option(node, source, "for") {
                    references.imports.extend(
                        modules(value, source, &scope)
                            .into_iter()
                            .map(|name| ("module".into(), name)),
                    );
                }
                let mut next = scope.clone();
                next.module = None;
                nested = Some(next);
            }
        } else if kind == "defdelegate"
            && let Some(value) = option(node, source, "to")
        {
            references.imports.extend(
                modules(value, source, &scope)
                    .into_iter()
                    .map(|name| ("module".into(), name)),
            );
        }
        if node.kind() == "dot"
            && node
                .child_by_field_name("right")
                .is_some_and(|right| right.kind() == "identifier")
            && let Some(name) = node
                .child_by_field_name("left")
                .and_then(|left| module(left, source, &scope))
        {
            references.imports.push(("module".into(), name));
        }
        if nested.is_none()
            && (matches!(
                node.kind(),
                "do_block" | "anonymous_function" | "stab_clause"
            ) || matches!(
                kind,
                "def" | "defp" | "defmacro" | "defmacrop" | "defguard" | "defguardp"
            ))
        {
            nested = Some(scope.clone());
        }
        if let Some(next) = nested {
            pending.push(Step::Restore(std::mem::replace(&mut scope, next)));
        }
        // Push children in reverse source order so aliases apply only to subsequent code.
        let mut cursor = node.walk();
        if cursor.goto_last_child() {
            loop {
                let child = cursor.node();
                if child.is_named() {
                    pending.push(Step::Enter(child));
                }
                if !cursor.goto_previous_sibling() {
                    break;
                }
            }
        }
    }
    references
}
