"""Define Tree-sitter captures for Python imports, docstrings, and outlines."""

from __future__ import annotations

IMPORT_QUERY = """
(import_statement) @import.statement
(import_from_statement
  module_name: [
    (dotted_name)
    (relative_import)
  ] @import.source
) @import.statement
"""

DOCSTRING_QUERY = """
(module
  . (comment)*
  . (expression_statement
    [(string) (concatenated_string) (parenthesized_expression)] @doc))

(class_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @doc)))

(function_definition
  body: (block
    . (comment)*
    . (expression_statement
      [(string) (concatenated_string) (parenthesized_expression)] @doc)))
"""

SKEL_QUERY = """
(class_definition
  name: (identifier) @skel.class.name
  ":" @header.end
  body: (block) @skel.class.body) @header.start

(function_definition
  name: (identifier) @skel.function.name
  parameters: (parameters) @skel.function.parameters
  ":" @header.end
  body: (block) @skel.function.body) @header.start

(decorator) @decorator

(class_definition
  body: (block
    . (expression_statement (string)) @doc))

(function_definition
  body: (block
    . (expression_statement (string)) @doc))
"""

SIGS_QUERY = """
(class_definition
  name: (identifier) @sigs.class.name
  ":" @header.end) @header.start

(function_definition
  name: (identifier) @sigs.function.name
  parameters: (parameters) @sigs.function.parameters
  ":" @header.end) @header.start
"""
