; Keep command names without arbitrary execution/logging payloads.
(normal_command (identifier) @header.start @header.end) @dependency

; Named project, target, variable, and configuration declarations.
(normal_command
  (identifier) @_name @header.start
  (argument_list . (argument) @header.end.inclusive)
  (#match? @_name "(?i)^(project|add_library|add_executable|add_custom_target|target_sources|target_link_libraries|target_include_directories|target_compile_definitions|target_compile_options|target_compile_features|set|option|find_package|cmake_minimum_required)$"))

[(function_command) (macro_command) (if_command) (elseif_command)
 (else_command) (foreach_command) (while_command) (block_command)] @header.start @header.end

(normal_command
  (identifier) @_name
  (#match? @_name "(?i)^(include|add_subdirectory)$")) @import.statement

; Retain declarative metadata and source lists, not custom commands or scripts.
(normal_command
  (identifier) @_name
  (#match? @_name "(?i)^(project|add_library|add_executable|target_sources|target_link_libraries|target_include_directories|target_compile_definitions|target_compile_options|target_compile_features|option|find_package|cmake_minimum_required)$")) @skel.doc

[(line_comment) (bracket_comment)] @docstring
