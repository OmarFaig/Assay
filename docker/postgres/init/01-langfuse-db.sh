#!/bin/bash
# Langfuse gets its own database on the same server, so the stack runs one
# Postgres instead of two. Runs once, on an empty data directory.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE DATABASE ${LANGFUSE_DB:-langfuse} OWNER $POSTGRES_USER;
EOSQL
