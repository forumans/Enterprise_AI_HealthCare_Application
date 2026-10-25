-- Migration 009: shared rate-limit counters, and gender values stored the one way.
--
-- 1. rate_limit_events: one row per counted event (failed login, reset request, self-registration) so
--    every Lambda instance sees the same counts and the limits in backend/app/core/rate_limit.py hold
--    globally instead of per instance. Keys (emails, client addresses) are stored only as SHA-256
--    hashes. Rows older than the longest window (1 hour) are deleted by the backend as it goes.
--    The table has no tenant_id (login happens before the tenant is known), so it has no RLS policy.
-- 2. patients.gender: admin-created patients were stored as "Male" / "Female" / "Other"; store the
--    gender_type values (MALE, FEMALE, OTHER, PREFER_NOT_TO_SAY) like every other path does.
--
-- Deploy order: either. Without this migration the backend counts in memory per instance, as before.
-- Requires migration 003. Idempotent: safe to run more than once. Run as the table owner.
--
--   AWS:   aws_env_spin_up\scripts\run-migration.ps1 -MigrationFiles <this file>
--   Local: psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 009_rate_limits_and_gender_values.sql
--
-- Rollback: 009_rate_limits_and_gender_values_rollback.sql (drops the table; gender values stay upper-case).

BEGIN;

CREATE TABLE IF NOT EXISTS public.rate_limit_events (
    id          uuid DEFAULT public.uuid_generate_v4() PRIMARY KEY,
    limit_name  varchar(32) NOT NULL,
    key_hash    char(64) NOT NULL,
    created_at  timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key ON public.rate_limit_events (limit_name, key_hash, created_at);
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_created ON public.rate_limit_events (created_at);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthcare_user') THEN
        GRANT SELECT, INSERT, DELETE ON public.rate_limit_events TO healthcare_user;
    END IF;
END $$;

UPDATE public.patients
   SET gender = upper(replace(trim(gender), ' ', '_'))
 WHERE gender IS NOT NULL
   AND gender <> upper(replace(trim(gender), ' ', '_'))
   AND upper(replace(trim(gender), ' ', '_')) IN ('MALE', 'FEMALE', 'OTHER', 'PREFER_NOT_TO_SAY');

COMMIT;

-- Check:
--   SELECT gender, count(*) FROM patients GROUP BY gender;
--   SELECT count(*) FROM rate_limit_events;
