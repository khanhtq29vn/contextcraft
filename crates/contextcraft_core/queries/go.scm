; Imports
(import_declaration) @import.statement
(import_spec) @dependency
(package_clause) @dependency

; Docstrings
(source_file
  (comment)+ @docstring @skel.doc
  . [
    (package_clause)
    (function_declaration)
    (method_declaration)
    (type_declaration)
    (const_declaration)
    (var_declaration)
  ])

; Headers
(function_declaration
  body: (block
    "{" @header.end)) @header.start

(method_declaration
  body: (block
    "{" @header.end)) @header.start

(function_declaration
  !body) @header.start @header.end

(method_declaration
  !body) @header.start @header.end

[
  (type_declaration)
] @header.start @header.end

; Skeleton extras
(package_clause) @skel.doc

; Keep declared names/types, not closures or large composite values.
(var_declaration "var" @header.start @header.end)
(const_declaration "const" @header.start @header.end)
[(var_spec name: (_) @header.start @header.end)
 (const_spec name: (_) @header.start @header.end)]
(var_spec name: (_) @header.start type: (_) @header.end.inclusive)
(const_spec name: (_) @header.start type: (_) @header.end.inclusive)
((comment) @dependency (#match? @dependency "^//go:embed[ \t]"))
