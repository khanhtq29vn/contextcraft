; Table headers, without their child assignments.
(table
  "[" @header.start
  "]" @header.end.inclusive)

(table_array_element
  "[[" @header.start
  "]]" @header.end.inclusive)

; Assignment keys, without their values.
(pair
  . [(bare_key) (quoted_key) (dotted_key)] @header.start
  "=" @header.end.inclusive)

; Keep scalar assignments and array entries in the skeleton.
(pair
  [(string) (integer) (float) (boolean)
   (offset_date_time) (local_date_time) (local_date) (local_time)]) @skel.doc

(array
  [(string) (integer) (float) (boolean)
   (offset_date_time) (local_date_time) (local_date) (local_time)] @skel.doc)

(comment) @docstring

(array ["[" "]"] @header.start @header.end)
(inline_table ["{" "}"] @header.start @header.end)
