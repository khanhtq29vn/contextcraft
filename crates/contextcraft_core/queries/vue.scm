[(doctype) (start_tag) (end_tag) (self_closing_tag) (interpolation)] @header.start @header.end
(text) @skel.doc
(comment) @docstring

[(start_tag) (self_closing_tag)] @dependency
[(script_element (raw_text) @dependency) (style_element (raw_text) @dependency)]
