(block (block_start) @header.end) @header.start
(attribute (identifier) @header.start "=" @header.end.inclusive)
(object_elem key: (expression) @header.start val: (expression) @header.end)

; Retain scalar configuration, not collection or template payloads.
(attribute (expression (literal_value))) @skel.doc
(object_elem val: (expression (literal_value))) @skel.doc
(comment) @docstring

(block) @dependency
(variable_expr) @dependency
