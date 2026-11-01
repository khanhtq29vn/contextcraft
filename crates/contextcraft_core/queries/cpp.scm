; C++ headers and declarations
(class_specifier
  body: (field_declaration_list "{" @header.end)) @header.start

(namespace_definition
  body: (declaration_list "{" @header.end)) @header.start

[
  (alias_declaration)
  (using_declaration)
  (concept_definition)
  (access_specifier)
] @header.start @header.end

(function_definition !body) @header.start @header.end
(function_definition body: (try_statement) @header.end) @header.start

; Keep template parameters with the declaration header, not implementation bodies.
(template_declaration
  (function_definition
    body: (compound_statement "{" @header.end))) @header.start

(template_declaration
  (class_specifier
    body: (field_declaration_list "{" @header.end))) @header.start

(template_declaration
  (struct_specifier
    body: (field_declaration_list "{" @header.end))) @header.start

(template_declaration
  [(declaration) (alias_declaration) (concept_definition)]) @header.start @header.end
