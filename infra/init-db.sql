-- ZeroTrace Postgres Initializer
-- Creates isolated databases for Orchestrator, AI Vector Memory, and Iceberg Catalog.

CREATE DATABASE zt_app;
CREATE DATABASE zt_rag;
CREATE DATABASE zt_catalog;

\c zt_rag;
CREATE EXTENSION IF NOT EXISTS vector;
