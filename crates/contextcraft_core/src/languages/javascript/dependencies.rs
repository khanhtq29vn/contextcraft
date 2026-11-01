//! Extract dependency references from captured syntax nodes.

use tree_sitter::Node;

/// Module-loading syntax used to choose relative path resolution rules.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImportKind {
    /// ECMAScript import or re-export, including dynamic `import()`.
    Module,
    /// CommonJS `require()` or TypeScript import assignment.
    Require,
}

/// Literal module reference extracted from JavaScript or TypeScript.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Import {
    /// Decoded module specifier.
    pub path: String,
    /// Module-loading syntax that produced this reference.
    pub kind: ImportKind,
}

/// Appends literal imports, re-exports, and supported module-loading calls.
///
/// Ignores malformed nodes and paths that are not string literals.
pub fn extract(node: Node<'_>, source: &[u8], imports: &mut Vec<Import>) {
    if node.has_error() {
        return;
    }

    let (path, kind) = match node.kind() {
        "import_statement" | "export_statement" => {
            (node.child_by_field_name("source"), ImportKind::Module)
        }
        "import_require_clause" => (node.child_by_field_name("source"), ImportKind::Require),
        "call_expression" => {
            let Some(function) = node.child_by_field_name("function") else {
                return;
            };
            let kind = if function.kind() == "import" {
                ImportKind::Module
            } else if function.kind() == "identifier"
                && function.utf8_text(source) == Ok("require")
                && node.child_by_field_name("optional_chain").is_none()
            {
                ImportKind::Require
            } else {
                return;
            };
            let Some(arguments) = node.child_by_field_name("arguments") else {
                return;
            };
            let mut cursor = arguments.walk();
            let mut arguments = arguments
                .named_children(&mut cursor)
                .filter(|argument| argument.kind() != "comment");
            let path = arguments.next();

            if kind == ImportKind::Require && arguments.next().is_some() {
                return;
            }

            (path, kind)
        }
        _ => return,
    };

    if let Some(path) = path
        && path.kind() == "string"
        && let Some(path) = path.utf8_text(source).ok().and_then(unquote)
    {
        imports.push(Import { path, kind });
    }
}

fn unquote(text: &str) -> Option<String> {
    let quote = text.chars().next()?;

    if !matches!(quote, '\'' | '"') || !text.ends_with(quote) || text.len() < 2 {
        return None;
    }

    let mut chars = text[1..text.len() - 1].chars().peekable();
    let mut units = Vec::new();

    while let Some(character) = chars.next() {
        let character = if character == '\\' {
            match chars.next()? {
                'b' => '\u{8}',
                'f' => '\u{c}',
                'n' => '\n',
                'r' => '\r',
                't' => '\t',
                'v' => '\u{b}',
                '0' if !chars.peek().is_some_and(char::is_ascii_digit) => '\0',
                '\n' | '\u{2028}' | '\u{2029}' => continue,
                '\r' => {
                    if chars.peek() == Some(&'\n') {
                        chars.next();
                    }
                    continue;
                }
                'x' => {
                    let value = chars.next()?.to_digit(16)? * 16 + chars.next()?.to_digit(16)?;
                    units.push(value as u16);
                    continue;
                }
                'u' => {
                    if chars.peek() == Some(&'{') {
                        chars.next();
                        let mut digits = String::new();

                        loop {
                            let digit = chars.next()?;

                            if digit == '}' {
                                break;
                            }
                            digits.push(digit);
                        }

                        char::from_u32(u32::from_str_radix(&digits, 16).ok()?)?
                    } else {
                        let mut value = 0;

                        for _ in 0..4 {
                            value = value * 16 + chars.next()?.to_digit(16)?;
                        }
                        units.push(value as u16);
                        continue;
                    }
                }
                '0'..='9' => return None,
                escaped => escaped,
            }
        } else {
            character
        };
        let mut buffer = [0; 2];
        units.extend_from_slice(character.encode_utf16(&mut buffer));
    }

    String::from_utf16(&units).ok()
}
