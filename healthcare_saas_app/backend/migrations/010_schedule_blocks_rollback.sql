-- Rollback of migration 010: restore the 002 sync_doctor_availability trigger and drop the range blocks.
-- Redeploy the previous backend build afterwards (the new one reads doctor_availability.block_id).
-- Slots blocked by ranges stay BLOCKED with their reason; booked slots in a block simply lose their flag.
--
--   psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 010_schedule_blocks_rollback.sql

BEGIN;

CREATE OR REPLACE FUNCTION public.sync_doctor_availability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN

    -- INSERT → book slot
    IF TG_OP = 'INSERT' THEN
        UPDATE doctor_availability
        SET status = 'BOOKED'
        WHERE doctor_id = NEW.doctor_id
        AND slot_time = NEW.appointment_time;

        RETURN NEW;
    END IF;

    -- UPDATE
    IF TG_OP = 'UPDATE' THEN

        -- if appointment cancelled → free slot
        IF NEW.status = 'CANCELLED' THEN
            UPDATE doctor_availability
            SET status = 'AVAILABLE'
            WHERE doctor_id = NEW.doctor_id
            AND slot_time = NEW.appointment_time;
        END IF;

        RETURN NEW;

    END IF;

    -- DELETE → free slot
    IF TG_OP = 'DELETE' THEN
        UPDATE doctor_availability
        SET status = 'AVAILABLE'
        WHERE doctor_id = OLD.doctor_id
        AND slot_time = OLD.appointment_time;

        RETURN OLD;
    END IF;

    RETURN NULL;

END;
$$;

DROP INDEX IF EXISTS public.idx_doctor_availability_block;
ALTER TABLE public.doctor_availability DROP COLUMN IF EXISTS block_id;
DROP TABLE IF EXISTS public.schedule_blocks;

COMMIT;
