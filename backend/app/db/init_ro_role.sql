-- ============================================================================
-- PostgreSQL Dedicated Read-Only Role Setup for QueryPilot
-- Enforces database-level read-only access for query execution and EXPLAIN.
-- ============================================================================

DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'querypilot_ro') THEN
        CREATE ROLE querypilot_ro WITH LOGIN PASSWORD 'querypilot_ro_pass';
    ELSE
        ALTER ROLE querypilot_ro WITH LOGIN PASSWORD 'querypilot_ro_pass';
    END IF;
END
$$;

-- Enforce read-only transactions at the role level
ALTER ROLE querypilot_ro SET default_transaction_read_only = on;
ALTER ROLE querypilot_ro SET statement_timeout = '5000ms';
ALTER ROLE querypilot_ro SET lock_timeout = '2000ms';

-- Grant connect and read-only privileges on public schema
GRANT CONNECT ON DATABASE querypilot TO querypilot_ro;
GRANT USAGE ON SCHEMA public TO querypilot_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO querypilot_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO querypilot_ro;

-- Explicitly revoke any write/create privileges on public schema
REVOKE CREATE ON SCHEMA public FROM querypilot_ro;
