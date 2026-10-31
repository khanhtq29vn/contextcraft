(using_directive) @import.statement @dependency
(file_scoped_namespace_declaration) @header.start @header.end @dependency
(namespace_declaration body: (_) @header.end) @header.start
(namespace_declaration !body) @header.start @header.end
(namespace_declaration) @dependency
(class_declaration body: (_) @header.end) @header.start
(class_declaration !body) @header.start @header.end
(class_declaration) @dependency
(struct_declaration body: (_) @header.end) @header.start
(struct_declaration !body) @header.start @header.end
(struct_declaration) @dependency
(interface_declaration body: (_) @header.end) @header.start
(interface_declaration !body) @header.start @header.end
(interface_declaration) @dependency
(record_declaration body: (_) @header.end) @header.start
(record_declaration !body) @header.start @header.end
(record_declaration) @dependency
(enum_declaration body: (_) @header.end) @header.start
(enum_declaration !body) @header.start @header.end
(enum_declaration) @dependency
(method_declaration body: (_) @header.end) @header.start
(method_declaration !body) @header.start @header.end
(constructor_declaration body: (_) @header.end) @header.start
(constructor_declaration !body) @header.start @header.end
(destructor_declaration body: (_) @header.end) @header.start
(destructor_declaration !body) @header.start @header.end
(operator_declaration body: (_) @header.end) @header.start
(operator_declaration !body) @header.start @header.end
(conversion_operator_declaration body: (_) @header.end) @header.start
(conversion_operator_declaration !body) @header.start @header.end
(local_function_statement body: (_) @header.end) @header.start
(local_function_statement !body) @header.start @header.end
(property_declaration accessors: (_) @header.end) @header.start
(property_declaration !accessors value: (_) @header.end) @header.start
(property_declaration !accessors !value) @header.start @header.end
(indexer_declaration accessors: (_) @header.end) @header.start
(indexer_declaration !accessors value: (_) @header.end) @header.start
(indexer_declaration !accessors !value) @header.start @header.end
(event_declaration accessors: (_) @header.end) @header.start
(accessor_declaration body: (_) @header.end) @header.start
(accessor_declaration !body) @header.start @header.end
(delegate_declaration) @header.start @header.end
(enum_member_declaration) @header.start @header.end
(field_declaration (variable_declaration type: (_) @header.end.inclusive)) @header.start
(field_declaration (variable_declaration (variable_declarator name: (_) @header.start @header.end)))
(event_field_declaration (variable_declaration type: (_) @header.end.inclusive)) @header.start
(event_field_declaration (variable_declaration (variable_declarator name: (_) @header.start @header.end)))
(attribute_list) @decorator
((comment) @docstring (#match? @docstring "^///|^/\\*\\*"))
