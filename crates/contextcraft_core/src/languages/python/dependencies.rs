//! Extract dependency references from captured syntax nodes.

use tree_sitter::Node;

/// One Python module import or `from` import statement.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Import {
    /// Module path components, without relative-import dots.
    pub module: Vec<String>,
    /// Number of leading dots. Zero denotes an absolute import.
    pub level: usize,
    /// Explicit alias of a direct module import, if present.
    pub alias: Option<String>,
    /// Names imported by a `from` statement.
    pub names: Vec<ImportedName>,
    /// Whether this reference came from a `from` statement.
    pub from: bool,
    /// Whether the statement imports `*` rather than named members.
    pub wildcard: bool,
}

/// One name and optional alias in a Python import statement.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ImportedName {
    /// Imported name split into dotted path components.
    pub path: Vec<String>,
    /// Explicit local alias, if present.
    pub alias: Option<String>,
}

/// Appends imports and imported names captured from a Python statement.
///
/// Ignores malformed nodes. Relative imports retain their leading-dot count.
pub fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>) {
    if node.has_error() {
        return;
    }

    let mut cursor = node.walk();
    let names: Vec<_> = node
        .children_by_field_name("name", &mut cursor)
        .map(|name| imported_name(name, source))
        .collect();

    if node.kind() == "import_statement" {
        for name in names {
            imports.push(Import {
                module: name.path,
                level: 0,
                alias: name.alias,
                names: Vec::new(),
                from: false,
                wildcard: false,
            });
        }
    } else if node.kind() == "import_from_statement" {
        let Some(module) = node.child_by_field_name("module_name") else {
            return;
        };

        let mut level = 0;
        let mut path = Vec::new();

        if module.kind() == "relative_import" {
            let mut cursor = module.walk();

            for child in module.named_children(&mut cursor) {
                match child.kind() {
                    "import_prefix" => {
                        level = child
                            .utf8_text(source)
                            .unwrap_or("")
                            .chars()
                            .filter(|&c| c == '.')
                            .count()
                    }

                    "dotted_name" => path = dotted_name(child, source),
                    _ => {}
                }
            }
        } else {
            path = dotted_name(module, source);
        }

        let mut cursor = node.walk();
        let wildcard = node
            .named_children(&mut cursor)
            .any(|child| child.kind() == "wildcard_import");

        imports.push(Import {
            module: path,
            level,
            alias: None,
            names,
            from: true,
            wildcard,
        });
    }
}

fn imported_name(node: Node<'_>, source: &[u8]) -> ImportedName {
    if node.kind() == "aliased_import" {
        ImportedName {
            path: node
                .child_by_field_name("name")
                .map(|name| dotted_name(name, source))
                .unwrap_or_default(),
            alias: node
                .child_by_field_name("alias")
                .and_then(|alias| alias.utf8_text(source).ok())
                .map(str::to_owned),
        }
    } else {
        ImportedName {
            path: dotted_name(node, source),
            alias: None,
        }
    }
}

fn dotted_name(node: Node<'_>, source: &[u8]) -> Vec<String> {
    let mut cursor = node.walk();

    node.named_children(&mut cursor)
        .filter(|child| child.kind() == "identifier")
        .filter_map(|child| child.utf8_text(source).ok().map(str::to_owned))
        .collect()
}
