(call_expression
  function: (identifier) @_macro @header.start
  type_arguments: (type_arguments) @header.end.inclusive
  (#any-of? @_macro "defineProps" "defineEmits" "defineSlots" "defineModel" "defineComponent"))
