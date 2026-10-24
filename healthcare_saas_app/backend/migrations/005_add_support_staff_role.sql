-- Migration 005: Support Staff role.
--
-- Adds SUPPORT_STAFF to the user_role enum and a support_staff profile table (same shape as admins).
-- Support staff are registered by admins and manage appointments and doctor availability on behalf
-- of patients and doctors.
--
-- Idempotent: safe to run more than once. Enum values can't be removed in PostgreSQL, so there is no
-- rollback script; an unused SUPPORT_STAFF value is harmless to older backend versions.
--
-- Run with:  psql -v ON_ERROR_STOP=1 -h <host> -U <user> -d <db> -f 005_add_support_staff_role.sql

BEGIN;

ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'SUPPORT_STAFF';

CREATE TABLE IF NOT EXISTS public.support_staff (
    id uuid DEFAULT public.uuid_generate_v4() PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    full_name character varying(255) NOT NULL,
    phone character varying(50),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp with time zone,
    deleted_by uuid REFERENCES public.users(id)
);

CREATE INDEX IF NOT EXISTS idx_support_staff_tenant ON public.support_staff (tenant_id);

DROP TRIGGER IF EXISTS audit_support_staff ON public.support_staff;
CREATE TRIGGER audit_support_staff
AFTER INSERT OR UPDATE OR DELETE ON public.support_staff
FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();

COMMIT;
