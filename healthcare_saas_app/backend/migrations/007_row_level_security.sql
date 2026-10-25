-- Migration 007: row-level security (tenant isolation inside PostgreSQL).
--
-- Every tenant table only shows and accepts rows whose tenant_id equals the transaction setting
-- app.current_tenant, which the backend sets from the signed login token at the start of each
-- transaction. A query that forgot its tenant filter therefore still can't read or write another
-- clinic's data. With no setting (no signed-in user), tenant tables appear empty.
--
-- The few lookups that must cross tenants before the tenant is known (login, password reset, email
-- uniqueness, first-admin check) go through the SECURITY DEFINER functions below, which return only
-- the columns they need. They run as the table owner, which RLS does not restrict (no FORCE).
--
-- Policies apply to the app's database user (healthcare_user), which must NOT own the tables or have
-- BYPASSRLS. Superusers and the table owner (the RDS master user) are not restricted, so migrations,
-- backups and maintenance keep working.
--
-- Requires migrations 003 and 005. Idempotent: safe to run more than once.
-- Deploy order: the backend works with or without this migration, so apply it after (or before)
-- deploying the backend that includes core/cross_tenant.py.
--
--   AWS:   aws_env_spin_up\scripts\run-migration.ps1 -MigrationFiles <this file>
--   Local: psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 007_row_level_security.sql
--
-- Rollback (if ever needed): for each table below, DROP POLICY tenant_isolation ON <table>;
-- ALTER TABLE <table> DISABLE ROW LEVEL SECURITY;

BEGIN;

CREATE OR REPLACE FUNCTION public.app_current_tenant() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.current_tenant', true), '')::uuid $$;

-- Cross-tenant lookups (SECURITY DEFINER, fixed search_path)

CREATE OR REPLACE FUNCTION public.app_login_lookup(p_email text)
    RETURNS TABLE (id uuid, tenant_id uuid, role public.user_role, password_hash text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
    AS $$
        SELECT u.id, u.tenant_id, u.role, u.password_hash FROM public.users u
        WHERE u.email = lower(p_email) AND u.deleted_at IS NULL AND u.is_active
        LIMIT 1
    $$;

CREATE OR REPLACE FUNCTION public.app_reset_lookup(p_user_id uuid)
    RETURNS TABLE (id uuid, tenant_id uuid, role public.user_role, password_hash text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
    AS $$
        SELECT u.id, u.tenant_id, u.role, u.password_hash FROM public.users u
        WHERE u.id = p_user_id AND u.deleted_at IS NULL AND u.is_active
    $$;

CREATE OR REPLACE FUNCTION public.app_email_in_use(p_email text, p_tenant uuid, p_exclude uuid)
    RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
    AS $$
        SELECT EXISTS (
            SELECT 1 FROM public.users u
            WHERE u.email = lower(p_email)
              AND (u.deleted_at IS NULL OR u.tenant_id = p_tenant)
              AND (p_exclude IS NULL OR u.id <> p_exclude)
        )
    $$;

CREATE OR REPLACE FUNCTION public.app_any_active_admin()
    RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
    AS $$
        SELECT EXISTS (SELECT 1 FROM public.users u WHERE u.role = 'ADMIN' AND u.is_active AND u.deleted_at IS NULL)
    $$;

REVOKE ALL ON FUNCTION public.app_login_lookup(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_reset_lookup(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_email_in_use(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_any_active_admin() FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthcare_user') THEN
        GRANT EXECUTE ON FUNCTION public.app_current_tenant() TO healthcare_user;
        GRANT EXECUTE ON FUNCTION public.app_login_lookup(text) TO healthcare_user;
        GRANT EXECUTE ON FUNCTION public.app_reset_lookup(uuid) TO healthcare_user;
        GRANT EXECUTE ON FUNCTION public.app_email_in_use(text, uuid, uuid) TO healthcare_user;
        GRANT EXECUTE ON FUNCTION public.app_any_active_admin() TO healthcare_user;
    END IF;
END $$;

-- Tenant isolation policy on every table that carries tenant_id

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'patients', 'doctors', 'support_staff', 'admins', 'doctor_availability', 'appointments',
        'medical_records', 'prescriptions', 'pharmacies', 'patient_documents', 'audit_logs'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON public.%I USING (tenant_id = public.app_current_tenant()) '
            'WITH CHECK (tenant_id = public.app_current_tenant())',
            t
        );
    END LOOP;
END $$;

COMMIT;

-- Check (as the app user, with no tenant set, should return 0):
--   SELECT count(*) FROM users;
