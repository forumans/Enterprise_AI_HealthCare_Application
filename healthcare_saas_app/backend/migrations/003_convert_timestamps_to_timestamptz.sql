-- Migration 003: convert every `timestamp without time zone` column in the public schema to
-- `timestamptz`, preserving the exact instant each value represents.
--
-- Why two source zones: naive timestamps carry no zone, so each column has to be interpreted in
-- the zone it was actually written in:
--   * Columns with a CURRENT_TIMESTAMP / now() default (created_at, audit_logs.performed_at) were
--     written by the database in its configured TimeZone (America/New_York on a default local
--     install; normally UTC on RDS).
--   * All other columns (slot_time, appointment_time, deleted_at, signed_at) are written by the
--     backend as naive UTC.
-- The DB zone defaults to the session's TimeZone setting. Override it if needed with
--   PGOPTIONS="-c migration.db_default_zone=UTC" psql ...
--
-- Safety:
--   * Runs in a single transaction - any error rolls back everything.
--   * Copies every affected value (by primary key) into schema tz_migration_backup first.
--   * After converting, checks every row: converting back to the source zone must reproduce the
--     original value exactly, and no row may be missing. Any mismatch aborts the transaction.
--   * Columns already of type timestamptz are skipped, but refuses to run if
--     tz_migration_backup already exists (drop it only after verifying a previous run).
--   * 003_convert_timestamps_to_timestamptz_rollback.sql reverses the conversion.
--
-- Run with:  psql -v ON_ERROR_STOP=1 -h <host> -U <user> -d <db> -f 003_convert_timestamps_to_timestamptz.sql
-- Deploy together with the backend code that uses timezone-aware datetimes (app/core/timeutils.py):
-- the old code binds naive datetimes, which asyncpg would misinterpret against timestamptz columns.

BEGIN;
SET LOCAL lock_timeout = '10s';

DO $$
DECLARE
    v_db_zone  text := coalesce(nullif(current_setting('migration.db_default_zone', true), ''),
                                current_setting('TimeZone'));
    v_table    text;
    v_cols     text;
    v_alters   text;
    v_bad      bigint;
    v_future   bigint;
    v_total    bigint := 0;
    p          record;
BEGIN
    IF to_regnamespace('tz_migration_backup') IS NOT NULL THEN
        RAISE EXCEPTION 'Schema tz_migration_backup already exists (from a previous run). '
            'Verify that run, then DROP SCHEMA tz_migration_backup CASCADE before running again.';
    END IF;

    -- Fail early on an invalid zone name.
    PERFORM now() AT TIME ZONE v_db_zone;
    RAISE NOTICE 'Interpreting CURRENT_TIMESTAMP-default columns as %, all other columns as UTC.', v_db_zone;

    CREATE SCHEMA tz_migration_backup;
    CREATE TABLE tz_migration_backup.column_plan (
        table_name  text NOT NULL,
        column_name text NOT NULL,
        source_zone text NOT NULL,
        PRIMARY KEY (table_name, column_name)
    );

    INSERT INTO tz_migration_backup.column_plan (table_name, column_name, source_zone)
    SELECT c.table_name, c.column_name,
           CASE WHEN c.column_default ~* '(current_timestamp|now\(\)|localtimestamp)' THEN v_db_zone ELSE 'UTC' END
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
    WHERE c.table_schema = 'public'
      AND c.data_type = 'timestamp without time zone';

    IF NOT EXISTS (SELECT 1 FROM tz_migration_backup.column_plan) THEN
        RAISE NOTICE 'No timestamp-without-time-zone columns found; nothing to do.';
        RETURN;
    END IF;

    -- 1. Back up original values, keyed by primary key `id`.
    FOR v_table IN SELECT DISTINCT table_name FROM tz_migration_backup.column_plan ORDER BY 1 LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = v_table AND column_name = 'id') THEN
            RAISE EXCEPTION 'Table public.% has no id column; cannot verify its conversion.', v_table;
        END IF;
        SELECT string_agg(format('%I', column_name), ', ' ORDER BY column_name) INTO v_cols
        FROM tz_migration_backup.column_plan WHERE table_name = v_table;
        EXECUTE format('CREATE TABLE tz_migration_backup.%I AS SELECT id, %s FROM public.%I', v_table, v_cols, v_table);
    END LOOP;

    -- 2. Convert, one ALTER (one table rewrite) per table.
    FOR v_table IN SELECT DISTINCT table_name FROM tz_migration_backup.column_plan ORDER BY 1 LOOP
        SELECT string_agg(format('ALTER COLUMN %I TYPE timestamptz USING %I AT TIME ZONE %L',
                                 column_name, column_name, source_zone), ', ' ORDER BY column_name)
          INTO v_alters
        FROM tz_migration_backup.column_plan WHERE table_name = v_table;
        EXECUTE format('ALTER TABLE public.%I %s', v_table, v_alters);
    END LOOP;

    -- 3. Verify every value round-trips exactly and no row was lost or added.
    FOR p IN SELECT * FROM tz_migration_backup.column_plan ORDER BY table_name, column_name LOOP
        EXECUTE format(
            'SELECT count(*) FROM tz_migration_backup.%1$I b FULL JOIN public.%1$I t ON t.id = b.id
             WHERE t.id IS NULL OR b.id IS NULL OR (t.%2$I AT TIME ZONE %3$L) IS DISTINCT FROM b.%2$I',
            p.table_name, p.column_name, p.source_zone) INTO v_bad;
        IF v_bad > 0 THEN
            RAISE EXCEPTION 'Verification failed for %.%: % row(s) differ from the backup. Rolled back.',
                p.table_name, p.column_name, v_bad;
        END IF;

        -- Sanity check on the zone assumption: values far in the future suggest the wrong source zone.
        IF p.source_zone <> 'UTC' THEN
            EXECUTE format('SELECT count(*) FROM public.%I WHERE %I > now() + interval ''1 hour''',
                           p.table_name, p.column_name) INTO v_future;
            IF v_future > 0 THEN
                RAISE WARNING '%.%: % value(s) are in the future after interpreting as % - double-check the DB zone.',
                    p.table_name, p.column_name, v_future, p.source_zone;
            END IF;
        END IF;

        EXECUTE format('SELECT count(*) FROM tz_migration_backup.%I', p.table_name) INTO v_bad;
        RAISE NOTICE 'Converted %.% (from %): % rows verified.', p.table_name, p.column_name, p.source_zone, v_bad;
        v_total := v_total + 1;
    END LOOP;

    RAISE NOTICE 'All % columns converted and verified. Backup kept in schema tz_migration_backup.', v_total;
END $$;

COMMIT;
