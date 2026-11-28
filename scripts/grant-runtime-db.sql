-- Run as the migration owner after migrations, in the TutBerry database.
-- Provision tutberry_app separately as LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT.
BEGIN;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM tutberry_app;
GRANT USAGE ON SCHEMA public TO tutberry_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM tutberry_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tutberry_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tutberry_app;
REVOKE UPDATE, DELETE, TRUNCATE ON tutberry_auditrecord FROM tutberry_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON django_migrations FROM tutberry_app;
COMMIT;
