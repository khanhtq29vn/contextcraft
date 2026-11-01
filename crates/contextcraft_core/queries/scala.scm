(import_declaration) @import.statement @dependency
(package_clause body: (_) @header.end) @header.start
(package_clause !body) @header.start @header.end
(package_clause) @dependency
(class_definition body: (_) @header.end) @header.start
(class_definition !body) @header.start @header.end
(class_definition) @dependency
(trait_definition body: (_) @header.end) @header.start
(trait_definition !body) @header.start @header.end
(trait_definition) @dependency
(object_definition body: (_) @header.end) @header.start
(object_definition !body) @header.start @header.end
(object_definition) @dependency
(enum_definition body: (_) @header.end) @header.start
(enum_definition) @dependency
(function_definition body: (_) @header.end) @header.start
(given_definition body: (_) @header.end) @header.start
(given_definition !body) @header.start @header.end
(given_definition) @dependency
(val_definition value: (_) @header.end) @header.start
(var_definition value: (_) @header.end) @header.start
(extension_definition parameters: (parameters) @header.end.inclusive) @header.start
[
  (function_declaration)
  (val_declaration)
  (var_declaration)
  (type_definition)
  (enum_case_definitions)
] @header.start @header.end
(annotation) @decorator
((block_comment) @docstring (#match? @docstring "^/\\*\\*"))

; Exported members can be imported through an object or package.
[(function_definition) (function_declaration) (val_definition) (var_definition) (val_declaration) (var_declaration) (type_definition)] @dependency
