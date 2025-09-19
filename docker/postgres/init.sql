-- Initialize PostgreSQL database with pgvector extension
-- This script runs automatically when the container starts

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify the extension is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
