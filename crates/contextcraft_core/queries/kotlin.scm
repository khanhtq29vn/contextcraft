(package_header) @header.start @header.end @dependency
(import) @import.statement @dependency
(file_annotation) @header.start @header.end
((block_comment) @docstring (#match? @docstring "^/\\*\\*"))

[
  (class_declaration)
  (object_declaration)
  (companion_object)
  (function_declaration)
  (property_declaration)
  (type_alias)
] @dependency
