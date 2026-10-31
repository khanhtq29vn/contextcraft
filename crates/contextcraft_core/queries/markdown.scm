; Docstrings
(paragraph) @docstring

; Headers
[
  (atx_heading)
  (setext_heading)
] @header.start @header.end

; Skeleton extras
(fenced_code_block) @skel.doc
(indented_code_block) @skel.doc
(link_reference_definition) @skel.doc

; Retain document structure beyond headings and prose.
(pipe_table_header) @header.start @header.end
(pipe_table) @skel.doc
(list_item (paragraph) @skel.doc)
(block_quote (paragraph) @skel.doc)

[(inline) (link_destination)] @dependency
