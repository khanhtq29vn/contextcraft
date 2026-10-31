; Block declarations retain all arguments, including defimpl's `for:` option.
(call
  target: (identifier) @_definition
  (arguments) @header.end.inclusive
  (do_block)
  (#any-of? @_definition "defmodule" "defprotocol" "defimpl" "def" "defp" "defmacro" "defmacrop")) @header.start

; The first argument is the declaration signature, not an inline `do:` body.
(call
  target: (identifier) @_definition
  (arguments . (_) @header.end.inclusive)
  (#any-of? @_definition "defmodule" "defprotocol" "defimpl" "def" "defp" "defmacro" "defmacrop" "defguard" "defguardp")) @header.start

(call
  target: (identifier) @_definition
  (#any-of? @_definition "defdelegate" "defstruct" "defexception" "defoverridable")) @header.start @header.end

(call
  target: (identifier) @_directive
  (#any-of? @_directive "alias" "import" "require" "use")) @import.statement @dependency

(unary_operator
  operator: "@"
  operand: (call target: (identifier) @_attribute)
  (#any-of? @_attribute "spec" "callback" "macrocallback" "type" "typep" "opaque" "optional_callbacks" "behaviour")) @header.start @header.end

(unary_operator
  operator: "@"
  operand: (call target: (identifier) @_attribute)
  (#any-of? @_attribute "doc" "moduledoc" "typedoc")) @docstring

(unary_operator
  operator: "@"
  operand: (call target: (identifier) @_attribute)
  (#any-of? @_attribute "impl" "derive" "enforce_keys")) @decorator

(call
  target: (identifier) @_definition
  (#any-of? @_definition "defmodule" "defprotocol" "defimpl")) @dependency
(dot) @dependency
