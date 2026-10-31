//! Extract dependency references from captured syntax nodes.

use tree_sitter::Node;

/// Package name and literal imports extracted from one Go source file.
#[derive(Debug, Default)]
pub struct Dependencies {
    /// Declared package name, if captured successfully.
    pub package: Option<String>,
    /// Decoded import paths in capture order.
    pub imports: Vec<String>,
    /// Static go:embed patterns.
    pub embeds: Vec<String>,
}

/// Records a package clause or appends an import path from a captured node.
///
/// Ignores malformed nodes and unrecognized import string escapes.
pub fn extract(node: Node<'_>, source: &[u8], dependencies: &mut Dependencies) {
    if node.has_error() {
        return;
    }

    if node.kind() == "comment" {
        if let Some(raw) = node
            .utf8_text(source)
            .ok()
            .and_then(|text| text.strip_prefix("//go:embed"))
        {
            let pattern = regex::Regex::new(r#""(?:[^"\\]|\\.)*"|`[^`]*`|[^\s]+"#).unwrap();
            for value in pattern.find_iter(raw).map(|value| value.as_str()) {
                if let Some(value) = if value.starts_with(['"', '`']) {
                    unquote(value)
                } else {
                    Some(value.to_owned())
                } {
                    dependencies.embeds.push(value);
                }
            }
        }
    } else if node.kind() == "package_clause" {
        let mut cursor = node.walk();
        dependencies.package = node
            .named_children(&mut cursor)
            .find(|child| child.kind() == "package_identifier")
            .and_then(|name| name.utf8_text(source).ok())
            .map(str::to_owned);
    } else if let Some(path) = node.child_by_field_name("path")
        && let Some(path) = path.utf8_text(source).ok().and_then(unquote)
    {
        dependencies.imports.push(path);
    }
}

pub(super) fn unquote(text: &str) -> Option<String> {
    if let Some(raw) = text.strip_prefix('`').and_then(|raw| raw.strip_suffix('`')) {
        return Some(raw.replace('\r', ""));
    }

    let mut chars = text.strip_prefix('"')?.strip_suffix('"')?.chars();
    let mut bytes = Vec::new();

    while let Some(character) = chars.next() {
        if character != '\\' {
            let mut buffer = [0; 4];
            bytes.extend_from_slice(character.encode_utf8(&mut buffer).as_bytes());
            continue;
        }

        let escaped = chars.next()?;
        let byte = match escaped {
            'a' => 7,
            'b' => 8,
            'f' => 12,
            'n' => b'\n',
            'r' => b'\r',
            't' => b'\t',
            'v' => 11,
            '\\' => b'\\',
            '"' => b'"',
            'x' | 'u' | 'U' | '0'..='7' => {
                let (radix, count, mut value) = match escaped {
                    'x' => (16, 2, 0),
                    'u' => (16, 4, 0),
                    'U' => (16, 8, 0),
                    digit => (8, 2, digit.to_digit(8)?),
                };

                for _ in 0..count {
                    value = value
                        .checked_mul(radix)?
                        .checked_add(chars.next()?.to_digit(radix)?)?;
                }

                if matches!(escaped, 'u' | 'U') {
                    let mut buffer = [0; 4];
                    bytes.extend_from_slice(
                        char::from_u32(value)?.encode_utf8(&mut buffer).as_bytes(),
                    );
                    continue;
                }

                u8::try_from(value).ok()?
            }
            _ => return None,
        };
        bytes.push(byte);
    }

    String::from_utf8(bytes).ok()
}
