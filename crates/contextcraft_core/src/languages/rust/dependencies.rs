//! Extract dependency references from captured syntax nodes.

use std::path::PathBuf;

use tree_sitter::Node;

/// Module declarations and imports extracted from one Rust source file.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct RustDependencies {
    /// Module declarations in capture order.
    pub modules: Vec<ModuleDeclaration>,
    /// Expanded imports in capture order.
    pub imports: Vec<Import>,
    /// Literal include!, include_str!, and include_bytes! paths.
    pub includes: Vec<String>,
}

/// A module declaration with its enclosing context and path attributes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModuleDeclaration {
    /// Enclosing inline module names, from outermost to innermost.
    pub context: Vec<String>,
    /// Declared module name, without a raw identifier prefix.
    pub name: String,
    /// Whether the module body is defined in this source file.
    pub inline: bool,
    /// Literal path from a recognized `#[path]` attribute, if present.
    pub path_override: Option<PathBuf>,
    /// Whether conflicting or unsupported path attributes prevent resolution.
    pub unresolved_path: bool,
    /// Whether this declaration or an ancestor has a direct `#[cfg(test)]` guard.
    pub test_only: bool,
}

/// An expanded Rust import with lexical context and resolution flags.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Import {
    /// Enclosing inline module names, from outermost to innermost.
    pub context: Vec<String>,
    /// Import path components, without raw identifier prefixes.
    pub path: Vec<String>,
    /// Explicit local alias, if present.
    pub alias: Option<String>,
    /// Whether the import ends in a wildcard.
    pub glob: bool,
    /// Whether the declaration has an explicit visibility modifier.
    pub public: bool,
    /// Whether the path is absolute or comes from `extern crate`.
    pub absolute: bool,
    /// Whether this is an `extern crate` declaration.
    pub external: bool,
    /// Whether the import is declared directly in a module scope.
    pub module_level: bool,
    /// Whether this import or an ancestor has a direct `#[cfg(test)]` guard.
    pub test_only: bool,
}

/// Appends module declarations and expanded imports from a captured node.
///
/// Retains enclosing module context, aliases, and directly recognized test guards.
pub fn extract(node: Node<'_>, source: &[u8], dependencies: &mut RustDependencies) {
    if node.has_error() {
        return;
    }

    if node.kind() == "macro_invocation" {
        let mut cursor = node.walk();
        if let Some(tokens) = node
            .named_children(&mut cursor)
            .find(|node| node.kind() == "token_tree")
        {
            let mut cursor = tokens.walk();
            let arguments: Vec<_> = tokens.named_children(&mut cursor).collect();
            if let [argument] = arguments.as_slice()
                && let Some(path) = string(*argument, source)
                && !path.contains('\0')
                && !std::path::Path::new(&path).is_absolute()
            {
                dependencies.includes.push(path);
            }
        }
        return;
    }

    let mut context = Vec::new();
    let mut module_level = true;
    let mut parent = node.parent();

    while let Some(ancestor) = parent {
        if ancestor.kind() == "mod_item" {
            if let Some(name) = ancestor.child_by_field_name("name") {
                context.push(text(name, source));
            }
        } else if !matches!(ancestor.kind(), "source_file" | "declaration_list") {
            module_level = false;
        }

        parent = ancestor.parent();
    }

    context.reverse();

    match node.kind() {
        "mod_item" if module_level => {
            let Some(name) = node.child_by_field_name("name") else {
                return;
            };

            let mut path_override = None;
            let mut unresolved_path = false;
            let mut previous = node.prev_named_sibling();

            while let Some(attribute_item) = previous {
                if matches!(attribute_item.kind(), "line_comment" | "block_comment") {
                    previous = attribute_item.prev_named_sibling();
                    continue;
                }

                if attribute_item.kind() != "attribute_item" {
                    break;
                }

                if let Some(attribute) = attribute_item.named_child(0)
                    && let Some(name) = attribute.named_child(0)
                {
                    if text(name, source) == "path" {
                        let path = attribute
                            .child_by_field_name("value")
                            .and_then(|value| string(value, source));

                        if path_override.is_some() || path.is_none() {
                            unresolved_path = true;
                        }

                        path_override = path.map(PathBuf::from);
                    } else if text(name, source) == "cfg_attr"
                        && attribute.utf8_text(source).unwrap_or("").contains("path")
                    {
                        unresolved_path = true;
                    }
                }

                previous = attribute_item.prev_named_sibling();
            }

            dependencies.modules.push(ModuleDeclaration {
                context,
                name: text(name, source),
                inline: node.child_by_field_name("body").is_some(),
                path_override,
                unresolved_path,
                test_only: test_only(node, source),
            });
        }

        "use_declaration" => {
            let Some(argument) = node.child_by_field_name("argument") else {
                return;
            };

            let mut cursor = node.walk();
            let public = node
                .named_children(&mut cursor)
                .any(|child| child.kind() == "visibility_modifier");
            let template = Import {
                context,
                path: Vec::new(),
                alias: None,
                glob: false,
                public,
                absolute: argument.utf8_text(source).unwrap_or("").starts_with("::"),
                external: false,
                module_level,
                test_only: test_only(node, source),
            };

            expand(argument, source, &[], &template, &mut dependencies.imports);
        }

        "extern_crate_declaration" => {
            let Some(name) = node.child_by_field_name("name") else {
                return;
            };

            dependencies.imports.push(Import {
                context,
                path: vec![text(name, source)],
                alias: node
                    .child_by_field_name("alias")
                    .map(|alias| text(alias, source)),
                glob: false,
                public: node
                    .utf8_text(source)
                    .unwrap_or("")
                    .trim_start()
                    .starts_with("pub"),
                absolute: true,
                external: true,
                module_level,
                test_only: test_only(node, source),
            });
        }

        _ => {}
    }
}

fn expand(
    node: Node<'_>,
    source: &[u8],
    prefix: &[String],
    template: &Import,
    imports: &mut Vec<Import>,
) {
    match node.kind() {
        "scoped_use_list" => {
            let mut template = template.clone();
            template.absolute |= node.utf8_text(source).unwrap_or("").starts_with("::");
            let mut path = prefix.to_vec();

            if let Some(parent) = node.child_by_field_name("path") {
                path.extend(segments(parent, source));
            }

            if let Some(list) = node.child_by_field_name("list") {
                expand(list, source, &path, &template, imports);
            }
        }

        "use_list" => {
            let mut cursor = node.walk();

            for child in node.named_children(&mut cursor) {
                expand(child, source, prefix, template, imports);
            }
        }

        "use_as_clause" => {
            let mut template = template.clone();
            template.alias = node
                .child_by_field_name("alias")
                .map(|alias| text(alias, source));

            if let Some(path) = node.child_by_field_name("path") {
                expand(path, source, prefix, &template, imports);
            }
        }

        "use_wildcard" => {
            let mut import = template.clone();
            import.absolute |= node.utf8_text(source).unwrap_or("").starts_with("::");
            import.path = prefix.to_vec();

            if let Some(path) = node.named_child(0) {
                import.path.extend(segments(path, source));
            }

            import.glob = true;
            imports.push(import);
        }

        "identifier" | "scoped_identifier" | "self" | "super" | "crate" => {
            let mut import = template.clone();
            import.absolute |= node.utf8_text(source).unwrap_or("").starts_with("::");
            import.path = prefix.to_vec();

            if node.kind() != "self" || prefix.is_empty() {
                import.path.extend(segments(node, source));
            }

            imports.push(import);
        }

        _ => {}
    }
}

fn segments(node: Node<'_>, source: &[u8]) -> Vec<String> {
    if node.kind() == "scoped_identifier" {
        let mut path = node
            .child_by_field_name("path")
            .map(|node| segments(node, source))
            .unwrap_or_default();

        if let Some(name) = node.child_by_field_name("name") {
            path.push(text(name, source));
        }

        path
    } else {
        vec![text(node, source)]
    }
}

fn text(node: Node<'_>, source: &[u8]) -> String {
    node.utf8_text(source)
        .unwrap_or("")
        .trim_start_matches("r#")
        .to_owned()
}

fn string(node: Node<'_>, source: &[u8]) -> Option<String> {
    if node.kind() == "raw_string_literal" {
        return Some(node.named_child(0)?.utf8_text(source).ok()?.to_owned());
    }

    if node.kind() != "string_literal" {
        return None;
    }

    let mut value = String::new();
    let mut cursor = node.walk();

    for child in node.named_children(&mut cursor) {
        let text = child.utf8_text(source).ok()?;

        if child.kind() == "string_content" {
            value.push_str(text);
        } else if child.kind() == "escape_sequence" {
            value.push(match text {
                "\\\\" => '\\',
                "\\\"" => '"',
                "\\n" => '\n',
                "\\r" => '\r',
                "\\t" => '\t',
                "\\0" => '\0',
                _ => return None,
            });
        } else {
            return None;
        }
    }

    Some(value)
}

fn test_only(mut node: Node<'_>, source: &[u8]) -> bool {
    loop {
        let mut previous = node.prev_named_sibling();

        while let Some(attribute) = previous {
            if !matches!(
                attribute.kind(),
                "attribute_item" | "line_comment" | "block_comment"
            ) {
                break;
            }

            if attribute.kind() == "attribute_item"
                && attribute
                    .utf8_text(source)
                    .unwrap_or("")
                    .chars()
                    .filter(|c| !c.is_whitespace())
                    .eq("#[cfg(test)]".chars())
            {
                return true;
            }

            previous = attribute.prev_named_sibling();
        }

        let Some(parent) = node.parent() else {
            return false;
        };

        node = parent;
    }
}

#[cfg(test)]
mod tests {
    use super::test_only;

    #[test]
    fn recognizes_test_configuration_with_whitespace() {
        let mut parser = tree_sitter::Parser::new();
        parser
            .set_language(&tree_sitter_rust::LANGUAGE.into())
            .unwrap();

        for (source, expected) in [
            ("#[cfg(test)] mod tests {}", true),
            ("#[cfg ( test )]\nmod tests {}", true),
            ("#[cfg(not(test))] mod production {}", false),
            ("mod production {}", false),
        ] {
            let tree = parser.parse(source, None).unwrap();
            let mut cursor = tree.root_node().walk();
            let module = tree
                .root_node()
                .named_children(&mut cursor)
                .find(|node| node.kind() == "mod_item")
                .unwrap();

            assert_eq!(test_only(module, source.as_bytes()), expected, "{source}");
        }
    }
}
