[(syntax) (edition) (package)] @header.start @header.end
(import) @import.statement @dependency

; Schema containers and RPC signatures, without option payloads.
(message (message_body) @header.end) @header.start
(enum (enum_body) @header.end) @header.start
(extend (message_body) @header.end) @header.start
(group (message_body) @header.end) @header.start
(oneof "{" @header.end) @header.start
(service "{" @header.end) @header.start
(rpc "{" @header.end) @header.start
(rpc ";" @header.end.inclusive) @header.start

; Wire identifiers, types, and tag numbers are essential at every source tier.
(field (field_number) @header.end.inclusive) @header.start
(map_field (field_number) @header.end.inclusive) @header.start
(oneof_field (field_number) @header.end.inclusive) @header.start
(enum_field (int_lit) @header.end.inclusive) @header.start
[(reserved) (extensions)] @header.start @header.end
(option (constant) @header.end) @header.start

; Scalar options and documentation enrich the skeleton; aggregate payloads do not.
(option (constant [(string) (int_lit) (float_lit) (bool) (full_ident)])) @skel.doc
(field_option (constant [(string) (int_lit) (float_lit) (bool) (full_ident)])) @skel.doc
(enum_value_option (constant [(string) (int_lit) (float_lit) (bool) (full_ident)])) @skel.doc
(comment) @docstring
