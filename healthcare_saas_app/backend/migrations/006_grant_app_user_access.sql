-- Migration 006: give the app's database user access to tables created by the master user.
--
-- On RDS the tables are owned by the master user (postgres) and the app connects as
-- healthcare_user. Unlike the local dev database, RDS has no default privileges for the app
-- user, so a table created by a migration (e.g. support_staff from 005) is unreadable to the app
-- until granted: the backend then fails with "permission denied for table support_staff".
--
-- This grants access to the existing tables and sets default privileges so tables and sequences
-- created by postgres in future migrations are usable by the app straight away.
-- Run as the master user (postgres). Idempotent: safe to run more than once.
--
--   AWS:   aws_env_spin_up\scripts\run-migration.ps1 -MigrationFiles <this file>
--   Local: psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 006_grant_app_user_access.sql

BEGIN;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO healthcare_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO healthcare_user;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO healthcare_user;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO healthcare_user;

COMMIT;

-- Check (should list no tables):
--   SELECT c.relname FROM pg_class c
--   WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')
--     AND NOT has_table_privilege('healthcare_user', c.oid, 'SELECT, INSERT, UPDATE, DELETE');
