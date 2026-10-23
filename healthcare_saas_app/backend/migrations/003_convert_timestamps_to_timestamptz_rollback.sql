-- Rollback for migration 003: convert the columns listed in tz_migration_backup.column_plan back to
-- `timestamp without time zone`, each in the zone it was originally stored in. Rows written after
-- migration 003 are converted the same way, so they match the pre-migration conventions.
--
-- Rows that existed before migration 003 are compared against the backup and differences are
-- reported (rows legitimately updated since the migration will show up there).
-- Deploy the previous backend code (naive datetimes) together with this rollback.
--
-- Run with:  psql -v ON_ERROR_STOP=1 -h <host> -U <user> -d <db> -f 003_convert_timestamps_to_timestamptz_rollback.sql

BEGIN;
SET LOCAL lock_timeout = '10s';

DO $$
DECLARE
    v_table  text;
    v_alters text;
    v_bad    bigint;
    p        record;
BEGIN
    IF to_regclass('tz_migration_backup.column_plan') IS NULL THEN
        RAISE EXCEPTION 'tz_migration_backup.column_plan not found - nothing to roll back (or the backup was dropped).';
    END IF;

    FOR v_table IN SELECT DISTINCT table_name FROM tz_migration_backup.column_plan ORDER BY 1 LOOP
        SELECT string_agg(format('ALTER COLUMN %I TYPE timestamp without time zone USING %I AT TIME ZONE %L',
                                 column_name, column_name, source_zone), ', ' ORDER BY column_name)
          INTO v_alters
        FROM tz_migration_backup.column_plan WHERE table_name = v_table;
        EXECUTE format('ALTER TABLE public.%I %s', v_table, v_alters);
    END LOOP;

    -- Pre-migration rows must match the backup exactly (deleted rows are allowed to be gone).
    FOR p IN SELECT * FROM tz_migration_backup.column_plan ORDER BY table_name, column_name LOOP
        EXECUTE format(
            'SELECT count(*) FROM tz_migration_backup.%1$I b JOIN public.%1$I t ON t.id = b.id
             WHERE t.%2$I IS DISTINCT FROM b.%2$I',
            p.table_name, p.column_name) INTO v_bad;
        IF v_bad > 0 THEN
            -- Not necessarily an error: the row may have been legitimately updated after migration 003.
            RAISE NOTICE '%.%: % pre-migration row(s) now differ from the backup (updated since migration?).',
                p.table_name, p.column_name, v_bad;
        END IF;
    END LOOP;

    RAISE NOTICE 'Rolled back to timestamp without time zone. Backup schema tz_migration_backup left in place.';
END $$;

COMMIT;
