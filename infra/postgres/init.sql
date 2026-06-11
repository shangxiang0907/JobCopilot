-- Creates supplemental databases on first PostgreSQL startup.
-- The primary `jobcopilot` database is created by POSTGRES_DB env var.
-- Temporal auto-creates its own databases; only Keycloak needs explicit creation here.

CREATE DATABASE keycloak;
