; Runtime compiler-macro contracts retain names, not validators or default factories.
(call_expression
  function: (identifier) @_macro @header.start @header.end
  (#any-of? @_macro "defineProps" "defineEmits" "defineSlots" "defineExpose" "defineModel" "defineOptions" "defineComponent"))
(call_expression
  function: (identifier) @_macro
  arguments: (arguments (object [(pair key: (_) @header.start @header.end) (shorthand_property_identifier) @header.start @header.end]))
  (#any-of? @_macro "defineProps" "defineEmits" "defineExpose" "defineOptions" "defineComponent"))
(call_expression
  function: (identifier) @_macro
  arguments: (arguments (array (string) @header.start @header.end))
  (#any-of? @_macro "defineProps" "defineEmits"))
(call_expression
  function: (identifier) @_macro
  arguments: (arguments (object (pair key: (_) @header.start value: (identifier) @header.end.inclusive)))
  (#eq? @_macro "defineProps"))

; Options API contracts, with and without defineComponent().
(export_statement value: (object (pair key: (_) @header.start @header.end)))
(export_statement value: (object (pair
  key: (property_identifier) @_option
  value: (object (pair key: (_) @header.start @header.end))))
  (#any-of? @_option "props" "emits" "components" "computed" "methods"))
(export_statement value: (object (pair
  key: (property_identifier) @_option
  value: (array (string) @header.start @header.end)))
  (#any-of? @_option "props" "emits"))
(call_expression
  function: (identifier) @_macro
  arguments: (arguments (object (pair
    key: (property_identifier) @_option
    value: (object (pair key: (_) @header.start @header.end)))))
  (#eq? @_macro "defineComponent")
  (#any-of? @_option "props" "emits" "components" "computed" "methods"))
(call_expression
  function: (identifier) @_macro
  arguments: (arguments (object (pair
    key: (property_identifier) @_option
    value: (array (string) @header.start @header.end))))
  (#eq? @_macro "defineComponent")
  (#any-of? @_option "props" "emits"))
