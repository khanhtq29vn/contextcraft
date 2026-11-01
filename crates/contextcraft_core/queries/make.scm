; Targets and prerequisites, without recipe commands.
(rule (targets) @header.start @header.end)
(rule (targets) @header.start normal: (prerequisites) @header.end.inclusive)
(rule (targets) @header.start order_only: (prerequisites) @header.end.inclusive)
(rule target: (pattern_list) @header.start prerequisite: (pattern_list) @header.end.inclusive)
(rule) @dependency

(variable_assignment name: (word) @header.start operator: _ @header.end.inclusive)
(shell_assignment name: (word) @header.start operator: _ @header.end.inclusive)
(define_directive "define" @header.start name: (word) @header.end.inclusive)
(VPATH_assignment name: _ @header.start operator: _ @header.end.inclusive)
(RECIPEPREFIX_assignment name: _ @header.start operator: _ @header.end.inclusive)

(include_directive) @import.statement @dependency
((variable_assignment) @skel.doc (#not-match? @skel.doc "[$\\r\\n]"))
(comment) @docstring

(variable_assignment) @dependency
