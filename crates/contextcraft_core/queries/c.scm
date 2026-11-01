; Includes
(preproc_include) @import.statement @dependency

; Documentation
((comment) @docstring @skel.doc
  (#match? @docstring "^(/\\*[*!]|//[/!])"))

; Function headers
(function_definition
  body: (compound_statement "{" @header.end)) @header.start

; Type and variable declarations, prototypes, and constants
[
  (type_definition)
  (enum_specifier)
  (preproc_def)
] @header.start @header.end

(struct_specifier
  body: (field_declaration_list "{" @header.end)) @header.start

(union_specifier
  body: (field_declaration_list "{" @header.end)) @header.start

(preproc_function_def
  value: (preproc_arg) @header.end) @header.start

(preproc_function_def !value) @header.start @header.end

; Split declarators from initializers, including C++ lambdas in shared queries.
(declaration type: (_) @_type @header.end.inclusive
  (#not-match? @_type "[{}]")) @header.start
(field_declaration type: (_) @_type @header.end.inclusive
  (#not-match? @_type "[{}]")) @header.start
(declaration declarator: (_) @header.start @header.end
  (#not-match? @header.start "="))
(field_declaration declarator: (_) @header.start @header.end
  (#not-match? @header.start "="))
(init_declarator declarator: (_) @header.start @header.end)
