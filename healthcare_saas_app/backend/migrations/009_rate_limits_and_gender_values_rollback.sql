-- Rollback of migration 009: drop the shared rate-limit counters. The backend then counts in memory per
-- instance again (no code change needed). Gender values normalized by 009 are left as they are.
--
--   psql -v ON_ERROR_STOP=1 -U postgres -d <db> -f 009_rate_limits_and_gender_values_rollback.sql

BEGIN;
DROP TABLE IF EXISTS public.rate_limit_events;
COMMIT;
