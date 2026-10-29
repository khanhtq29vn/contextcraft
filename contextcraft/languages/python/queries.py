"""Define Tree-sitter captures for Python imports, docstrings, and outlines."""

from __future__ import annotations

IMPORT_QUERY = """
(import_statement) @import.statement
(import_from_statement
  module_name: [
    (dotted_name)
    (relative_import)
  ]
) @import.statement
"""

DOCSTRING_QUERY = """
(module
  . (comment)*
  . (expression_statement
    [(string) (concatenated_string) (parenthesized_expression)] @docstring))

(class_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @docstring)))

(function_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @docstring)))
"""

SKEL_EXTRAS_QUERY = """
(decorator) @decorator

(class_definition
  body: (block
    . (expression_statement (string)) @skel.doc))

(function_definition
  body: (block
    . (expression_statement (string)) @skel.doc))
"""

HEADER_QUERY = """
(class_definition
  name: (identifier)
  ":" @header.end) @header.start

(function_definition
  name: (identifier)
  parameters: (parameters)
  ":" @header.end) @header.start
"""

ANALYSIS_QUERY = IMPORT_QUERY + DOCSTRING_QUERY + HEADER_QUERY + SKEL_EXTRAS_QUERY
