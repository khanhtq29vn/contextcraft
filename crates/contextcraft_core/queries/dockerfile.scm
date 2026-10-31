; Preserve build structure and metadata, but not executable command payloads.
[
  (from_instruction)
  (workdir_instruction)
  (user_instruction)
  (expose_instruction)
  (volume_instruction)
  (stopsignal_instruction)
] @header.start @header.end

; Stop before heredoc content while keeping all source/destination operands.
(copy_instruction (path) @header.end.inclusive) @header.start
(copy_instruction (json_string_array) @header.end.inclusive) @header.start
(add_instruction (path) @header.end.inclusive) @header.start
(add_instruction (json_string_array) @header.end.inclusive) @header.start

(arg_instruction . (arg_pair name: (_) @header.end.inclusive)) @header.start
(arg_pair name: (_) @header.start @header.end)
(env_instruction . (env_pair name: (_) @header.end.inclusive)) @header.start
(env_pair name: (_) @header.start @header.end)
(label_instruction . (label_pair key: (_) @header.end.inclusive)) @header.start
(label_pair key: (_) @header.start @header.end)
(run_instruction "RUN" @header.start @header.end)
(cmd_instruction "CMD" @header.start @header.end)
(entrypoint_instruction "ENTRYPOINT" @header.start @header.end)
(healthcheck_instruction "HEALTHCHECK" @header.start @header.end)
(healthcheck_instruction "NONE" @header.end.inclusive) @header.start
(shell_instruction "SHELL" @header.start @header.end)
(onbuild_instruction "ONBUILD" @header.start @header.end)

[(arg_instruction) (env_instruction) (label_instruction) (comment)] @skel.doc
[(copy_instruction) (add_instruction) (from_instruction)] @dependency
