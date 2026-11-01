; Imports
(use_declaration) @import.statement @dependency
(extern_crate_declaration) @import.statement @dependency
(mod_item) @dependency

; Docstrings
(line_comment
  doc: (doc_comment)) @docstring

(block_comment
  doc: (doc_comment)) @docstring

; Headers
(function_item
  body: (block
    "{" @header.end)) @header.start

(struct_item
  body: (field_declaration_list
    "{" @header.end)) @header.start

(struct_item
  ";" @header.end) @header.start

(enum_item
  body: (enum_variant_list
    "{" @header.end)) @header.start

(trait_item
  body: (declaration_list
    "{" @header.end)) @header.start

(impl_item
  body: (declaration_list
    "{" @header.end)) @header.start

(mod_item
  body: (declaration_list
    "{" @header.end)) @header.start

(mod_item
  ";" @header.end) @header.start

; Skeleton extras
(attribute_item) @decorator
(inner_attribute_item) @decorator

; Public API members and declarations, without initializer bodies.
[(field_declaration) (enum_variant) (function_signature_item) (type_item)
 (associated_type)] @header.start @header.end
(const_item type: (_) @header.end.inclusive) @header.start
(static_item type: (_) @header.end.inclusive) @header.start
(macro_definition name: (_) @header.end.inclusive) @header.start
(macro_invocation macro: (_) @_macro
  (#any-of? @_macro "include" "include_str" "include_bytes")) @dependency
