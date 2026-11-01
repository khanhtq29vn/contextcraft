; Preserve document structure. Embedded code is outlined by the language supplement.
[
  (doctype)
  (start_tag)
  (end_tag)
  (self_closing_tag)
] @header.start @header.end

; Keep document titles and headings in the skeleton.
(element
  (start_tag (tag_name) @_tag)
  (text) @skel.doc
  (#match? @_tag "(?i)^(title|h[1-6])$"))

(comment) @docstring

[(start_tag) (self_closing_tag)] @dependency

[(script_element (raw_text) @dependency) (style_element (raw_text) @dependency)]
