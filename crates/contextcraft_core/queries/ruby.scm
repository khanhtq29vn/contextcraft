; Body fields also cover endless methods.
(class body: (_) @header.end) @header.start
(class !body) @header.start @header.end
(module body: (_) @header.end) @header.start
(module !body) @header.start @header.end
(method body: (_) @header.end) @header.start
(method !body) @header.start @header.end
(singleton_method body: (_) @header.end) @header.start
(singleton_method !body) @header.start @header.end
(singleton_class body: (_) @header.end) @header.start
(singleton_class !body) @header.start @header.end

(assignment left: (constant) @header.start right: (_) @header.end)
(call method: (identifier) @_method
  (#any-of? @_method "require" "require_relative" "load" "autoload")) @import.statement @dependency
(call method: (identifier) @_method
  (#any-of? @_method "attr_reader" "attr_writer" "attr_accessor" "include" "extend" "prepend")) @header.start @header.end
(comment) @docstring

(assignment left: (constant) right: [(integer) (float) (string) (true) (false) (nil)]) @skel.doc
