-- Migration 008: a time zone per clinic (tenants.timezone).
--
-- Until now one CLINIC_TIMEZONE served every clinic of a deployment. Each clinic now has its own IANA
-- zone, which drives its office hours (8 AM-11 PM local), clinic days and weeks, and how the browser
-- shows times. Existing clinics keep the zone they have been running in, so nothing moves.
--
-- That zone defaults to America/New_York (the old CLINIC_TIMEZONE default); if the deployment ran
-- with a different CLINIC_TIMEZONE, pass the same value:
--   PGOPTIONS="-c migration.clinic_timezone=America/Chicago" psql ...
-- Clinics inserted later without a zone get the same default. Admins can change their clinic's zone
-- in the app (Admin > Clinic Settings).
--
-- Deploy order: apply this migration BEFORE deploying the backend that reads tenants.timezone. The
-- previous backend ignores the new column, so applying it early is safe.
-- Requires migration 003. Idempotent: safe to run more than once. Run as the table owner.
--
--   AWS:   aws_env_spin_up\scripts\run-migration.ps1 -MigrationFiles <this file>
--   Local: psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 008_add_tenant_timezone.sql
--
-- Rollback (if ever needed): ALTER TABLE tenants DROP COLUMN timezone;  (with the previous backend)

BEGIN;

DO $$
DECLARE
    v_zone text := coalesce(nullif(current_setting('migration.clinic_timezone', true), ''), 'America/New_York');
BEGIN
    -- Fails with "time zone ... not recognized" for a misspelled zone, before anything changes
    PERFORM now() AT TIME ZONE v_zone;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenants' AND column_name = 'timezone'
    ) THEN
        EXECUTE format('ALTER TABLE public.tenants ADD COLUMN timezone varchar(64) NOT NULL DEFAULT %L', v_zone);
    END IF;
END $$;

COMMIT;

-- Check:
--   SELECT name, timezone FROM tenants;
