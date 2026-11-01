; Imports
(import_statement) @import.statement @dependency
(import_from_statement
  module_name: [
    (dotted_name)
    (relative_import)
  ]
) @import.statement @dependency

; Docstrings
(module
  . (comment)*
  . (expression_statement
    [(string) (concatenated_string) (parenthesized_expression)] @docstring))

(class_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @docstring)))

(function_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @docstring)))

; Headers
(class_definition
  name: (identifier)
  ":" @header.end) @header.start

(function_definition
  name: (identifier)
  parameters: (parameters)
  ":" @header.end) @header.start

; Skeleton extras
(decorator) @decorator

(class_definition
  body: (block
    . (expression_statement (string)) @skel.doc))

(function_definition
  body: (block
    . (expression_statement (string)) @skel.doc))

; Module and class declarations, not function-local implementation variables.
(module (expression_statement (assignment left: (_) @header.start @header.end)))
(module (expression_statement (assignment left: (_) @header.start type: (_) @header.end.inclusive)))
(class_definition body: (block (expression_statement (assignment left: (_) @header.start @header.end))))
(class_definition body: (block (expression_statement (assignment left: (_) @header.start type: (_) @header.end.inclusive))))
(type_alias_statement) @header.start @header.end
