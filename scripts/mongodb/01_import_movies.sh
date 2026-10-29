#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Task 1 - Import movies.json into MongoDB
#          database: entertainment   collection: movies
#
# Run in the TERMINAL (bash), not inside the Mongo shell.
#
# Credentials are read from environment variables, never hardcoded:
#   export MONGO_USER=root
#   export MONGO_PASSWORD='...'      # if unset, mongoimport prompts for it
#   export MONGO_HOST=mongo          # default: mongo
# -----------------------------------------------------------------------------
set -euo pipefail

MONGO_HOST="${MONGO_HOST:-mongo}"
MONGO_USER="${MONGO_USER:-root}"
DATA_FILE="${1:-data/movies.json}"

AUTH_ARGS=(-u "${MONGO_USER}" --authenticationDatabase admin)
if [ -n "${MONGO_PASSWORD:-}" ]; then
  AUTH_ARGS+=(-p "${MONGO_PASSWORD}")
fi

mongoimport "${AUTH_ARGS[@]}" \
  --host "${MONGO_HOST}" \
  --db entertainment \
  --collection movies \
  --file "${DATA_FILE}"

# Expected output:
#   connected to: mongodb://mongo/
#   100 document(s) imported successfully. 0 document(s) failed to import.
#
# Re-running is safe (idempotent): every document has an explicit _id, so a
# second run fails per document with E11000 duplicate key errors instead of
# silently creating 100 duplicates.
