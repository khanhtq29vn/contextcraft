//! Kotlin package-qualified declarations and explicit imports.

use tree_sitter as ts;

use crate::languages::local::{References, text};

fn identifier(value: &str) -> String {
    value
        .split('.')
        .map(|part| part.trim_matches('`'))
        .collect::<Vec<_>>()
        .join(".")
}

pub(super) fn extract(nodes: &[ts::Node<'_>], source: &[u8]) -> References {
    let mut references = References::default();
    let package = nodes
        .iter()
        .find(|node| node.kind() == "package_header")
        .and_then(|node| {
            let mut cursor = node.walk();
            node.named_children(&mut cursor)
                .find(|node| node.kind() == "qualified_identifier")
        })
        .map(|node| identifier(text(node, source)))
        .unwrap_or_default();
    for &node in nodes {
        if node.has_error() || node.kind() == "package_header" {
            continue;
        }
        if node.kind() == "import" {
            let mut cursor = node.walk();
            if let Some(name) = node
                .named_children(&mut cursor)
                .find(|node| node.kind() == "qualified_identifier")
            {
                let mut cursor = node.walk();
                let wildcard = node.children(&mut cursor).any(|node| node.kind() == "*");
                references.imports.push((
                    if wildcard { "namespace" } else { "type" }.into(),
                    identifier(text(name, source)),
                ));
            }
            continue;
        }
        let mut parents = Vec::new();
        let mut parent = node.parent();
        let mut local = false;
        while let Some(ancestor) = parent {
            if matches!(
                ancestor.kind(),
                "function_body"
                    | "block"
                    | "lambda_literal"
                    | "object_literal"
                    | "anonymous_initializer"
            ) {
                local = true;
                break;
            }
            if matches!(
                ancestor.kind(),
                "class_declaration" | "object_declaration" | "companion_object"
            ) {
                let name = ancestor
                    .child_by_field_name("name")
                    .map_or("Companion", |name| text(name, source));
                parents.push(identifier(name));
            }
            parent = ancestor.parent();
        }
        if local {
            continue;
        }
        parents.reverse();
        if !package.is_empty() {
            parents.insert(0, package.clone());
        }
        let mut names = Vec::new();
        if node.kind() == "property_declaration" {
            let mut cursor = node.walk();
            for variable in node
                .named_children(&mut cursor)
                .filter(|node| node.kind() == "variable_declaration")
            {
                let mut cursor = variable.walk();
                if let Some(name) = variable
                    .named_children(&mut cursor)
                    .find(|node| node.kind() == "identifier")
                {
                    names.push(identifier(text(name, source)));
                }
            }
        } else if let Some(name) = node
            .child_by_field_name("name")
            .or_else(|| node.child_by_field_name("type"))
        {
            names.push(identifier(text(name, source)));
        } else if node.kind() == "companion_object" {
            names.push("Companion".into());
        }
        for name in names {
            let mut qualified = parents.clone();
            qualified.push(name);
            references.exports.push(qualified.join("."));
        }
    }
    references
}
