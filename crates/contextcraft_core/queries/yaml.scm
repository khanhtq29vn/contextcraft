; Mapping keys and separators, in both block and flow mappings.
(block_mapping_pair
  key: (_) @header.start
  ":" @header.end.inclusive)

(flow_pair
  key: (_) @header.start
  ":" @header.end.inclusive)

; Keep scalar properties, excluding nested collections and block payloads.
(block_mapping_pair
  value: (flow_node
    [(plain_scalar) (single_quote_scalar) (double_quote_scalar) (alias)])) @skel.doc

(flow_pair
  value: (flow_node
    [(plain_scalar) (single_quote_scalar) (double_quote_scalar) (alias)])) @skel.doc

(comment) @docstring

(block_sequence_item "-" @header.start @header.end)
(flow_sequence ["[" "]"] @header.start @header.end)
(flow_mapping ["{" "}"] @header.start @header.end)
[(anchor) (alias)] @skel.doc
