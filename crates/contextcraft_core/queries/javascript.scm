; Imports and re-exports
(import_statement) @import.statement @dependency
(export_statement source: (string)) @import.statement @dependency

((call_expression
  function: (identifier) @_callee) @dependency
  (#eq? @_callee "require"))

(call_expression function: (import)) @dependency

; Documentation
((comment) @docstring @skel.doc
  (#match? @docstring "^/\\*\\*"))

; Headers
(function_declaration body: (statement_block "{" @header.end)) @header.start
(generator_function_declaration body: (statement_block "{" @header.end)) @header.start
(class_declaration body: (class_body "{" @header.end)) @header.start
(method_definition body: (statement_block "{" @header.end)) @header.start

(variable_declarator
  value: (arrow_function body: (_) @header.end)) @header.start

(variable_declarator
  value: (function_expression body: (statement_block "{" @header.end))) @header.start

; Skeleton extras
(decorator) @decorator

; Value APIs retain their names, never arbitrary initializer payloads.
(program [(lexical_declaration (variable_declarator name: (_) @header.start @header.end))
          (variable_declaration (variable_declarator name: (_) @header.start @header.end))])
(export_statement declaration: [(lexical_declaration (variable_declarator name: (_) @header.start @header.end))
                                (variable_declaration (variable_declarator name: (_) @header.start @header.end))])
(program [(lexical_declaration (variable_declarator value: (object (pair key: (_) @header.start @header.end))))
          (variable_declaration (variable_declarator value: (object (pair key: (_) @header.start @header.end))))])
(export_statement declaration: (lexical_declaration (variable_declarator value: (object (pair key: (_) @header.start @header.end)))))
(assignment_expression left: (member_expression) @_export @header.start @header.end
  (#match? @_export "^(module\\.exports|exports\\.[A-Za-z_$][A-Za-z0-9_$]*)$"))
(assignment_expression left: (member_expression) @_export right: (object (pair key: (_) @header.start @header.end))
  (#eq? @_export "module.exports"))
