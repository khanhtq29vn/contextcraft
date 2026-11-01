[
  (doctype) (start_tag) (end_tag) (self_closing_tag)
  (expression) (expression_tag) (html_tag) (render_tag) (const_tag) (debug_tag)
  (if_start) (else_if_start) (else_start) (if_end)
  (each_start) (each_end) (await_start) (then_start) (catch_start) (await_end)
  (key_start) (key_end) (snippet_start) (snippet_end)
] @header.start @header.end
(text) @skel.doc
(comment) @docstring

[(start_tag) (self_closing_tag)] @dependency
[(script_element (raw_text) @dependency) (style_element (raw_text) @dependency)]
