; Stylesheet structure and declaration names.
(rule_set (selectors) @header.start @header.end)
(declaration ":" @header.end.inclusive) @header.start
(nested_declaration (block) @header.end) @header.start
(media_statement (block) @header.end) @header.start
(supports_statement (block) @header.end) @header.start
(keyframes_statement (keyframes_name) @header.end.inclusive) @header.start
(keyframe_block (block) @header.end) @header.start
(at_rule (at_keyword) @header.start @header.end)
(at_rule (block) @header.end) @header.start
(at_rule ";" @header.end.inclusive) @header.start
[(charset_statement) (namespace_statement) (postcss_statement)] @header.start @header.end

; Sass declarations and control-flow headers, without executable bodies.
(mixin_statement (block) @header.end) @header.start
(function_statement (block) @header.end) @header.start
(include_statement "@include" @header.start (identifier) @header.end.inclusive)
(extend_statement) @header.start @header.end
(at_root_statement (block) @header.end) @header.start
(if_statement (block) @header.end) @header.start
(else_if_clause (block) @header.end) @header.start
(else_clause (block) @header.end) @header.start
(each_statement (block) @header.end) @header.start
(for_statement (block) @header.end) @header.start
(while_statement (block) @header.end) @header.start

[(import_statement) (use_statement) (forward_statement)] @import.statement @dependency
(declaration) @skel.doc
[(comment) (js_comment)] @docstring

(call_expression (function_name) @_url (#eq? @_url "url")) @dependency
