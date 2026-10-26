-- Migration 010: range blocks of a doctor's schedule, and freed hours that stay blocked.
--
-- 1. schedule_blocks: one row per range block ("Vacation Nov 3-7"), half-open [start_time, end_time) in UTC,
--    with a reason category and optional note. Rows are never deleted by the app: unblocking the last
--    hour of a block sets released_at/released_by. Tenant-isolated by row-level security like every
--    other tenant table (migration 007), and audited by the DB-level audit trigger.
-- 2. doctor_availability.block_id: "the doctor wants this hour blocked". A BOOKED slot with a block_id is
--    an appointment that needs rescheduling. ON DELETE SET NULL, indexed on (doctor_id, block_id).
-- 3. sync_doctor_availability (trigger on appointments) frees a slot by the release rule: BLOCKED if the
--    slot has a block_id (keeping the block's reason), AVAILABLE otherwise. Until the first range block
--    every block_id is NULL, so behaviour is unchanged. It now reacts only to the change INTO
--    CANCELLED (and to deleting a live appointment), and only frees a slot that is BOOKED, so touching an
--    already-cancelled appointment can't free a slot someone else has booked since.
--
-- Deploy order: apply this migration BEFORE deploying the backend that reads doctor_availability.block_id.
-- Requires migrations 003 and 007. Idempotent: safe to run more than once. Run as the table owner.
--
--   AWS:   aws_env_spin_up\scripts\run-migration.ps1 -MigrationFiles <this file>
--   Local: psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 010_schedule_blocks.sql
--
-- Rollback: 010_schedule_blocks_rollback.sql (restores the 002 trigger, drops the column and the table).

BEGIN;

CREATE TABLE IF NOT EXISTS public.schedule_blocks (
    id               uuid DEFAULT public.uuid_generate_v4() PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    doctor_id        uuid NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    start_time       timestamp with time zone NOT NULL,
    end_time         timestamp with time zone NOT NULL,
    reason_category  varchar(32) NOT NULL,
    reason_note      varchar(500),
    created_by       uuid REFERENCES public.users(id),
    created_at       timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    released_at      timestamp with time zone,
    released_by      uuid REFERENCES public.users(id),
    CONSTRAINT schedule_blocks_reason_category_check
        CHECK (reason_category IN ('VACATION', 'CONFERENCE', 'SICK', 'PERSONAL', 'ADMINISTRATIVE', 'OTHER')),
    CONSTRAINT schedule_blocks_range_check CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_schedule_blocks_doctor ON public.schedule_blocks (doctor_id, start_time);
CREATE INDEX IF NOT EXISTS idx_schedule_blocks_tenant ON public.schedule_blocks (tenant_id);

ALTER TABLE public.doctor_availability
    ADD COLUMN IF NOT EXISTS block_id uuid REFERENCES public.schedule_blocks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_doctor_availability_block ON public.doctor_availability (doctor_id, block_id);

-- Row-level security, as in 007
ALTER TABLE public.schedule_blocks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.schedule_blocks;
CREATE POLICY tenant_isolation ON public.schedule_blocks
    USING (tenant_id = public.app_current_tenant())
    WITH CHECK (tenant_id = public.app_current_tenant());

-- The app user's access, as in 006 (the default privileges only cover tables created by postgres)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthcare_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.schedule_blocks TO healthcare_user;
    END IF;
END $$;

-- DB-level audit safety net (the app also writes one audit entry per block action)
DROP TRIGGER IF EXISTS audit_schedule_blocks ON public.schedule_blocks;
CREATE TRIGGER audit_schedule_blocks
AFTER INSERT OR UPDATE OR DELETE ON public.schedule_blocks
FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_function();

-- Release rule: a freed slot stays BLOCKED when the doctor wants the hour blocked
CREATE OR REPLACE FUNCTION public.sync_doctor_availability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN

    -- INSERT → book slot (block_id is kept: a booked slot with a block needs rescheduling)
    IF TG_OP = 'INSERT' THEN
        UPDATE doctor_availability
        SET status = 'BOOKED'
        WHERE doctor_id = NEW.doctor_id
        AND slot_time = NEW.appointment_time;

        RETURN NEW;
    END IF;

    -- UPDATE → appointment cancelled: release its slot
    IF TG_OP = 'UPDATE' THEN
        IF NEW.status = 'CANCELLED' AND OLD.status IS DISTINCT FROM 'CANCELLED' THEN
            UPDATE doctor_availability
            SET status = CASE WHEN block_id IS NOT NULL THEN 'BLOCKED' ELSE 'AVAILABLE' END::slot_status,
                block_reason = CASE WHEN block_id IS NOT NULL THEN block_reason END
            WHERE doctor_id = NEW.doctor_id
            AND slot_time = NEW.appointment_time
            AND status = 'BOOKED';
        END IF;

        RETURN NEW;
    END IF;

    -- DELETE → live appointment removed: release its slot
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IS DISTINCT FROM 'CANCELLED' THEN
            UPDATE doctor_availability
            SET status = CASE WHEN block_id IS NOT NULL THEN 'BLOCKED' ELSE 'AVAILABLE' END::slot_status,
                block_reason = CASE WHEN block_id IS NOT NULL THEN block_reason END
            WHERE doctor_id = OLD.doctor_id
            AND slot_time = OLD.appointment_time
            AND status = 'BOOKED';
        END IF;

        RETURN OLD;
    END IF;

    RETURN NULL;

END;
$$;

DROP TRIGGER IF EXISTS trg_sync_availability ON public.appointments;
CREATE TRIGGER trg_sync_availability
AFTER INSERT OR UPDATE OR DELETE
ON public.appointments
FOR EACH ROW
EXECUTE FUNCTION public.sync_doctor_availability();

COMMIT;

-- Check:
--   SELECT count(*) FROM schedule_blocks;
--   SELECT status, count(*) FILTER (WHERE block_id IS NOT NULL) FROM doctor_availability GROUP BY status;
