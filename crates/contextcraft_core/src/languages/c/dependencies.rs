//! Extract dependency references from captured syntax nodes.

use tree_sitter::Node;

/// Appends quoted include paths captured by `node`.
///
/// Ignores system includes, malformed nodes, and nonliteral paths.
pub fn extract(node: Node<'_>, source: &[u8], includes: &mut Vec<String>) {
    if node.kind() != "preproc_include" || node.has_error() {
        return;
    }

    let Some(path) = node.child_by_field_name("path") else {
        return;
    };

    if path.kind() == "system_lib_string" {
        if let Ok(value) = path.utf8_text(source) {
            includes.push(value.to_owned());
        }
        return;
    }
    if path.kind() != "string_literal" {
        return;
    }

    if let Ok(text) = path.utf8_text(source)
        && let Some(path) = text
            .strip_prefix('"')
            .and_then(|text| text.strip_suffix('"'))
        && !path.is_empty()
    {
        // Header names are not C string escapes; only preprocessing line splices apply.
        includes.push(path.replace("\\\r\n", "").replace("\\\n", ""));
    }
}
