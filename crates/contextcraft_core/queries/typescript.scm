; TypeScript import assignments
(import_require_clause) @dependency

; Type declarations
[
  (interface_declaration)
  (type_alias_declaration)
  (enum_declaration)
  (function_signature)
  (abstract_method_signature)
] @header.start @header.end

(abstract_class_declaration body: (class_body "{" @header.end)) @header.start

(public_field_definition value: (_) @header.end) @header.start
(public_field_definition !value) @header.start @header.end
(program (lexical_declaration (variable_declarator name: (_) @header.start type: (_) @header.end.inclusive)))
(export_statement declaration: (lexical_declaration (variable_declarator name: (_) @header.start type: (_) @header.end.inclusive)))
(ambient_declaration (lexical_declaration (variable_declarator name: (_) @header.start @header.end)))
(ambient_declaration (lexical_declaration (variable_declarator name: (_) @header.start type: (_) @header.end.inclusive)))
[(property_signature) (method_signature) (index_signature)] @header.start @header.end
