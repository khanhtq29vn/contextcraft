(program) @dependency
(php_tag) @header.start @header.end
(namespace_definition body: (_) @header.end) @header.start
(namespace_definition !body) @header.start @header.end
(namespace_use_declaration) @import.statement
(use_declaration) @import.statement

(class_declaration body: (_) @header.end) @header.start
(interface_declaration body: (_) @header.end) @header.start
(trait_declaration body: (_) @header.end) @header.start
(enum_declaration body: (_) @header.end) @header.start
(function_definition body: (_) @header.end) @header.start
(method_declaration body: (_) @header.end) @header.start
(method_declaration !body) @header.start @header.end
(enum_case) @header.start @header.end

[(include_expression) (include_once_expression) (require_expression) (require_once_expression)] @import.statement
((comment) @docstring (#match? @docstring "^/\\*\\*"))
