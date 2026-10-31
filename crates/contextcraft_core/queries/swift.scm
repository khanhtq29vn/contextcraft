(import_declaration) @import.statement @dependency
(class_declaration body: (_) @header.end) @header.start
(class_declaration !body) @header.start @header.end
(protocol_declaration body: (_) @header.end) @header.start
(function_declaration body: (_) @header.end) @header.start
(function_declaration !body) @header.start @header.end
(init_declaration body: (_) @header.end) @header.start
(init_declaration !body) @header.start @header.end
(deinit_declaration body: (_) @header.end) @header.start
(deinit_declaration !body) @header.start @header.end
(property_declaration computed_value: (_) @header.end) @header.start
(property_declaration !computed_value value: (_) @header.end) @header.start
(property_declaration !computed_value !value (type_annotation) @header.end.inclusive) @header.start
(subscript_declaration (computed_property) @header.end) @header.start
(subscript_declaration (function_body) @header.end) @header.start
[
  (protocol_function_declaration)
  (protocol_property_declaration)
  (typealias_declaration)
  (associatedtype_declaration)
  (enum_entry)
] @header.start @header.end
(attribute) @decorator
((comment) @docstring (#match? @docstring "^///"))
((multiline_comment) @docstring (#match? @docstring "^/\\*\\*"))
