-- LR 4A: compare query plans on the same dataset.
-- Run only on a disposable development/test database.
-- The fixture is committed before index DDL to avoid pending FK trigger events.
-- Use a disposable database; the fixture is removed after both measurements.
BEGIN;

-- Create a disposable listing so the benchmark works on a fresh CI database.
INSERT INTO tutberry_listingrecord (id, owner_id, title, daily_rate, deposit, status, category, location)
VALUES ('11111111-1111-4111-8111-111111111111',
        '22222222-2222-4222-8222-222222222222',
        'EXPLAIN fixture', 100.00, 0.00, 'active', 'tools', 'test');

-- Generate a repeatable set of cancelled bookings for one tenant.
-- The exclusion constraint still applies to every generated row.
WITH selected_listing AS (
    SELECT id FROM tutberry_listingrecord WHERE id = '11111111-1111-4111-8111-111111111111'
)
INSERT INTO tutberry_bookingrecord
    (id, listing_id, tenant_id, start_date, end_date, rent, deposit, status, cancellation_reason)
SELECT
    gen_random_uuid(), selected_listing.id, '00000000-0000-0000-0000-000000000001'::uuid,
    DATE '2100-01-01' + i,
    DATE '2100-01-01' + i,
    100.00, 0.00, 'cancelled', NULL
FROM selected_listing, generate_series(0, 29999) AS i;

COMMIT;
ANALYZE tutberry_bookingrecord;

-- Compare tenant query without/with the specific B-tree index.
-- Index is dropped temporarily inside a rollback-only transaction.
DROP INDEX IF EXISTS booking_tenant_recent_idx;
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, start_date
FROM tutberry_bookingrecord
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'
ORDER BY start_date DESC LIMIT 20;

CREATE INDEX booking_tenant_recent_idx
ON tutberry_bookingrecord (tenant_id, start_date DESC);
ANALYZE tutberry_bookingrecord;
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, start_date
FROM tutberry_bookingrecord
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'
ORDER BY start_date DESC LIMIT 20;

-- Remove benchmark rows and fixture, keeping the migration-created index.
DELETE FROM tutberry_bookingrecord
WHERE listing_id = '11111111-1111-4111-8111-111111111111';
DELETE FROM tutberry_listingrecord
WHERE id = '11111111-1111-4111-8111-111111111111';
ANALYZE tutberry_bookingrecord;
