(package_declaration) @header.start @header.end @dependency
(import_declaration) @import.statement @dependency

(class_declaration body: (_) @header.end) @header.start @dependency
(interface_declaration body: (_) @header.end) @header.start @dependency
(enum_declaration body: (_) @header.end) @header.start @dependency
(record_declaration body: (_) @header.end) @header.start @dependency
(annotation_type_declaration body: (_) @header.end) @header.start @dependency
(method_declaration body: (_) @header.end) @header.start
(method_declaration !body) @header.start @header.end
(constructor_declaration body: (_) @header.end) @header.start
(compact_constructor_declaration body: (_) @header.end) @header.start
(annotation_type_element_declaration) @header.start @header.end

[(type_identifier) (scoped_type_identifier)] @dependency
((block_comment) @docstring (#match? @docstring "^/\\*\\*"))
(enum_constant name: (_) @header.end.inclusive) @header.start

(module_declaration body: (_) @header.end) @header.start
[(exports_module_directive) (opens_module_directive) (provides_module_directive)
 (requires_module_directive) (uses_module_directive)] @header.start @header.end
