(section) @header.start @header.end
(target) @header.start @header.end
(directive ".." @header.start "::" @header.end.inclusive)
(directive ".." @header.start body: (body (arguments) @header.end.inclusive))
(directive) @dependency

(paragraph) @docstring
(options) @skel.doc
