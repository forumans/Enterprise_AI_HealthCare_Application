-- Migration 004: one-time backfill of the new evening office-hour slots (5 PM - 11 PM clinic local
-- time) for the next 7 days, after working hours were extended from 8 AM-4 PM to 8 AM-11 PM.
--
-- The backend only generates default slots for doctors with NO upcoming slots, so doctors who
-- already have 8 AM-4 PM slots would otherwise not get evening slots until those run out.
-- Only doctors that already have upcoming slots are backfilled: giving evening slots to a doctor
-- with none would stop the backend from generating their 8 AM-4 PM defaults. Slots that already
-- exist are left untouched, and earlier hours are never re-created (a doctor may have removed them).
--
-- Requires migration 003 (slot_time must be timestamptz). DST-safe: local hours are converted to
-- UTC with the IANA zone rules for each calendar day.
-- Clinic zone defaults to America/New_York (same default as CLINIC_TIMEZONE in the backend);
-- override with PGOPTIONS="-c migration.clinic_timezone=America/Chicago" psql ...
--
-- Run with:  psql -v ON_ERROR_STOP=1 -h <host> -U <user> -d <db> -f 004_backfill_evening_availability_slots.sql

BEGIN;

DO $$
DECLARE
    v_zone     text := coalesce(nullif(current_setting('migration.clinic_timezone', true), ''), 'America/New_York');
    v_inserted bigint;
BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'doctor_availability' AND column_name = 'slot_time')
       <> 'timestamp with time zone' THEN
        RAISE EXCEPTION 'doctor_availability.slot_time is not timestamptz - run migration 003 first.';
    END IF;

    INSERT INTO doctor_availability (tenant_id, doctor_id, slot_time, status)
    SELECT d.tenant_id, d.id, s.slot_time, 'AVAILABLE'
    FROM doctors d
    CROSS JOIN generate_series(0, 6)   AS day_offset
    CROSS JOIN generate_series(17, 23) AS hr          -- 5 PM through the 11 PM slot
    CROSS JOIN LATERAL (
        SELECT (((now() AT TIME ZONE v_zone)::date + day_offset) + make_interval(hours => hr))
               AT TIME ZONE v_zone AS slot_time
    ) s
    WHERE d.deleted_at IS NULL
      AND s.slot_time > now()
      AND EXISTS (SELECT 1 FROM doctor_availability a
                  WHERE a.doctor_id = d.id AND a.slot_time > now())
      AND NOT EXISTS (SELECT 1 FROM doctor_availability a
                      WHERE a.doctor_id = d.id AND a.slot_time = s.slot_time);

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'Inserted % evening slot(s) (clinic zone %).', v_inserted, v_zone;
END $$;

COMMIT;
