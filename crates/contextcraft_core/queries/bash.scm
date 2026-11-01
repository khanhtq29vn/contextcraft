(function_definition body: (_) @header.end) @header.start
(program (variable_assignment name: (_) @header.start value: (_) @header.end))
(program (declaration_command (variable_assignment value: (_) @header.end) @header.start))
(program (declaration_command (variable_name) @header.start @header.end))
(command name: (command_name) @_name
  (#any-of? @_name "source" ".")) @import.statement @dependency
(comment) @docstring

; Control-flow headers without command payloads.
(if_statement condition: (_) @header.end.inclusive) @header.start
(for_statement body: (do_group) @header.end) @header.start
(while_statement body: (do_group) @header.end) @header.start
(case_statement value: (_) @header.end.inclusive) @header.start
