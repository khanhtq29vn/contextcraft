; Schema headers without field bodies or leading descriptions.
(object_type_definition "type" @header.start (name) @header.end.inclusive)
(object_type_definition "type" @header.start (fields_definition) @header.end)
(interface_type_definition "interface" @header.start (name) @header.end.inclusive)
(interface_type_definition "interface" @header.start (fields_definition) @header.end)
(input_object_type_definition "input" @header.start (name) @header.end.inclusive)
(input_object_type_definition "input" @header.start (input_fields_definition) @header.end)
(enum_type_definition "enum" @header.start (name) @header.end.inclusive)
(schema_definition "schema" @header.start @header.end)
(scalar_type_definition "scalar" @header.start (name) @header.end.inclusive)
(union_type_definition "union" @header.start (union_member_types) @header.end.inclusive)
(directive_definition "directive" @header.start (directive_locations) @header.end.inclusive)

; Extensions have no leading descriptions.
(object_type_extension (fields_definition) @header.end) @header.start
(interface_type_extension (fields_definition) @header.end) @header.start
(input_object_type_extension (input_fields_definition) @header.end) @header.start
(enum_type_extension (name) @header.end.inclusive) @header.start
(schema_extension "schema" @header.end.inclusive) @header.start
[(scalar_type_extension) (union_type_extension) (root_operation_type_definition)] @header.start @header.end

(field_definition (name) @header.start (type) @header.end.inclusive)
(input_value_definition (name) @header.start (type) @header.end.inclusive)
(enum_value_definition (enum_value) @header.start @header.end)

; Executable document outlines.
(operation_definition (operation_type) @header.start (selection_set) @header.end)
(fragment_definition (selection_set) @header.end) @header.start
(fragment_definition) @dependency
(fragment_spread) @header.start @header.end @dependency
(field (selection_set) @header.end) @header.start
(field (name) @header.start @header.end)

(description) @docstring
[(default_value) (directive)] @skel.doc
((comment) @import.statement @dependency
  (#match? @import.statement "^#\\s*import\\s"))
