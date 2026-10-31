; Root anchoring prevents routine-body statements from entering the outline.
(source_file (toplevel_stmt (stmt [
  (CreateStmt) (DefineStmt) (CreateDomainStmt) (CreateSeqStmt)
  (CreateExtensionStmt) (IndexStmt) (CreateTrigStmt)
  (AlterTableStmt) (AlterEnumStmt) (AlterTypeStmt) (AlterCompositeTypeStmt)
  (DropStmt)
] @header.start @header.end)))

; Schema elements may contain views and other statements; retain only the header.
(source_file (toplevel_stmt (stmt (CreateSchemaStmt [(opt_single_name) (ColId) (RoleSpec)] @header.end.inclusive) @header.start)))

; Views keep definitions only in SKEL; table-as-query omits its data query.
(source_file (toplevel_stmt (stmt (ViewStmt (SelectStmt) @header.end) @header.start)))
(source_file (toplevel_stmt (stmt (CreateMatViewStmt (SelectStmt) @header.end) @header.start)))
(source_file (toplevel_stmt (stmt (CreateAsStmt (SelectStmt) @header.end) @header.start)))
(source_file (toplevel_stmt (stmt [(ViewStmt (SelectStmt) @skel.doc) (CreateMatViewStmt (SelectStmt) @skel.doc)])))

; Functions and procedures retain parameters and return types, never AS/body options.
(source_file (toplevel_stmt (stmt (CreateFunctionStmt (func_args_with_defaults) @header.end.inclusive) @header.start)))
(source_file (toplevel_stmt (stmt (CreateFunctionStmt (func_return) @header.end.inclusive) @header.start)))
(source_file (toplevel_stmt (stmt (CreateFunctionStmt (table_func_column_list) @header.end.inclusive) @header.start)))

; Start at the operation keyword to exclude CTE payloads preceding it.
(source_file (toplevel_stmt (stmt (InsertStmt (kw_insert) @header.start (insert_target) @header.end.inclusive))))
(source_file (toplevel_stmt (stmt (UpdateStmt (kw_update) @header.start (relation_expr_opt_alias) @header.end.inclusive))))
(source_file (toplevel_stmt (stmt (DeleteStmt (kw_delete) @header.start (relation_expr_opt_alias) @header.end.inclusive))))
(source_file (toplevel_stmt (stmt (CopyStmt (kw_copy) @header.start (qualified_name) @header.end.inclusive))))

(source_file (toplevel_stmt (stmt (CommentStmt) @skel.doc)))
(source_file (comment) @docstring)

; Standalone queries retain the operation, not expressions or row payloads.
(source_file (toplevel_stmt (stmt (SelectStmt (select_no_parens (simple_select (kw_select) @header.start @header.end))))))
(source_file (toplevel_stmt (stmt (MergeStmt (kw_merge) @header.start (relation_expr_opt_alias) @header.end.inclusive))))

; Additional static schema migrations and access-control declarations.
(source_file (toplevel_stmt (stmt [
  (RenameStmt)
  (AlterObjectSchemaStmt)
  (AlterOwnerStmt)
  (GrantStmt)
  (GrantRoleStmt)
  (CreatePolicyStmt)
  (AlterPolicyStmt)
  (CreateEventTrigStmt)
  (RefreshMatViewStmt)
  (CreateStatsStmt)
  (CreateCastStmt)
  (CreateTransformStmt)
  (AlterSeqStmt)
  (AlterExtensionStmt)
  (AlterExtensionContentsStmt)
  (AlterDomainStmt)
  (AlterFunctionStmt)
  (AlterDefaultPrivilegesStmt)
  (CreateForeignTableStmt)
] @header.start @header.end)))
