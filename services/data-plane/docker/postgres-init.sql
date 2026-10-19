-- Create additional databases for ZeroTrace
CREATE DATABASE zt_rag;
CREATE DATABASE zt_catalog;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE zt_rag TO ztuser;
GRANT ALL PRIVILEGES ON DATABASE zt_catalog TO ztuser;

-- Enable pgvector in zt_rag
\c zt_rag
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pgvector in zt_app too (for any future relational PII tables)
\c zt_app
CREATE EXTENSION IF NOT EXISTS vector;
