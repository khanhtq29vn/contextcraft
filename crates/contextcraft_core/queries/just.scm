(recipe_header) @header.start @header.end @dependency
(alias) @header.start @header.end @dependency
(assignment left: (identifier) @header.start ":=" @header.end.inclusive)
(setting) @header.start @header.end
[(import) (module)] @import.statement @dependency

(attribute) @decorator
(comment) @docstring
(assignment right: (expression (value (string)))) @skel.doc

(source_file) @dependency
