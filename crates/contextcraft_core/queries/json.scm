; Keys and separators form a structural outline, not executable JSON.
(pair
  key: (string) @header.start
  ":" @header.end.inclusive)

; Keep scalar properties and array entries in the skeleton.
(pair
  value: [(string) (number) (true) (false) (null)]) @skel.doc

(array
  [(string) (number) (true) (false) (null)] @skel.doc)

; Preserve container structure in both outline tiers.
(object ["{" "}"] @header.start @header.end)
(array ["[" "]"] @header.start @header.end)
