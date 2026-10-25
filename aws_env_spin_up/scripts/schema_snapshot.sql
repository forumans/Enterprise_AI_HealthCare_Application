-- Read-only snapshot of the public schema, used to compare the local and AWS databases.
-- Returns one JSON document; run-migration.ps1 -SchemaSnapshot executes it on RDS as the app user.
SELECT json_build_object(
  'columns', (SELECT json_agg(x ORDER BY x) FROM (
      SELECT format('%s.%s %s %s default=%s', table_name, column_name, data_type,
                    CASE WHEN is_nullable = 'YES' THEN 'null' ELSE 'not-null' END, coalesce(column_default, '-')) AS x
      FROM information_schema.columns WHERE table_schema = 'public') s),
  'enums', (SELECT json_agg(x ORDER BY x) FROM (
      SELECT format('%s: %s', t.typname, string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)) AS x
      FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
      WHERE t.typnamespace = 'public'::regnamespace GROUP BY t.typname) s),
  'indexes', (SELECT json_agg(indexdef ORDER BY indexdef) FROM pg_indexes WHERE schemaname = 'public'),
  'constraints', (SELECT json_agg(x ORDER BY x) FROM (
      SELECT format('%s %s: %s', conrelid::regclass, conname, pg_get_constraintdef(oid)) AS x
      FROM pg_constraint WHERE connamespace = 'public'::regnamespace) s),
  'triggers', (SELECT json_agg(x ORDER BY x) FROM (
      SELECT format('%s %s: %s', tgrelid::regclass, tgname, pg_get_triggerdef(oid)) AS x
      FROM pg_trigger WHERE NOT tgisinternal AND tgrelid::regclass::text NOT LIKE 'pg_%') s),
  'functions', (SELECT json_agg(x ORDER BY x) FROM (
      SELECT format('%s(%s) md5=%s', p.proname, pg_get_function_identity_arguments(p.oid), md5(p.prosrc)) AS x
      FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace) s),
  'rls_tables', (SELECT coalesce(json_agg(relname ORDER BY relname), '[]') FROM pg_class
      WHERE relnamespace = 'public'::regnamespace AND relrowsecurity),
  'policies', (SELECT coalesce(json_agg(x ORDER BY x), '[]') FROM (
      SELECT format('%s %s: using %s / check %s', tablename, policyname, qual, with_check) AS x
      FROM pg_policies WHERE schemaname = 'public') s),
  'extensions', (SELECT json_agg(x ORDER BY x) FROM (SELECT extname AS x FROM pg_extension) s),
  'schemas', (SELECT json_agg(nspname ORDER BY nspname) FROM pg_namespace
              WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'),
  'app_user_missing_access', (SELECT coalesce(json_agg(c.relname ORDER BY c.relname), '[]') FROM pg_class c
      WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')
        AND NOT has_table_privilege(current_user, c.oid, 'SELECT, INSERT, UPDATE, DELETE')),
  'settings', json_build_object('server_version', current_setting('server_version'),
                                'TimeZone', current_setting('TimeZone'),
                                'server_encoding', current_setting('server_encoding'))
)::text
