; Rules and conditional headers, without declaration values.
(rule_set (selectors) @header.start @header.end)
(declaration ":" @header.end.inclusive) @header.start
(media_statement (block) @header.end) @header.start
(supports_statement (block) @header.end) @header.start
(scope_statement (block) @header.end) @header.start
(keyframes_statement (keyframes_name) @header.end.inclusive) @header.start
(keyframe_block (block) @header.end) @header.start
(at_rule (at_keyword) @header.start @header.end)
(at_rule (block) @header.end) @header.start
(at_rule ";" @header.end.inclusive) @header.start
[(charset_statement) (namespace_statement) (postcss_statement)] @header.start @header.end

(import_statement) @import.statement @dependency
(declaration) @skel.doc
[(comment) (js_comment)] @docstring

(call_expression (function_name) @_url (#eq? @_url "url")) @dependency
