(program) @dependency
((comment) @docstring (#match? @docstring "^#'"))
(call function: (identifier) @import.name
  (#match? @import.name "^(library|require|requireNamespace|loadNamespace|source|sys\\.source|import|importFrom|export|exportPattern|S3method|useDynLib)$")) @import.statement
