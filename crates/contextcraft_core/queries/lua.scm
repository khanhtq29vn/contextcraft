; Functions, including empty and anonymous function declarations.
(function_declaration parameters: (parameters) @header.end.inclusive) @header.start
(function_definition parameters: (parameters) @header.end.inclusive) @header.start
(variable_declaration (assignment_statement (expression_list) @header.end)) @header.start
(variable_declaration (variable_list) @header.start @header.end)
(function_call name: (identifier) @_name
  (#any-of? @_name "require" "dofile" "loadfile")) @import.statement @dependency
(comment) @docstring

(assignment_statement (variable_list) @header.start @header.end)
