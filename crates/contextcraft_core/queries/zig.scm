((comment) @docstring (#match? @docstring "^//(/([^/]|$)|!)"))

(builtin_function
  (builtin_identifier) @_builtin
  (#any-of? @_builtin "@import" "@embedFile")) @dependency
