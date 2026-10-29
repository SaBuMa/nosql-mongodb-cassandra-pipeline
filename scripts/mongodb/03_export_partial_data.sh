#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Task 5 - Export _id, title, year, rating and Director to partial_data.csv
#
# Run in the TERMINAL (bash). Same connection arguments as the import,
# opposite direction.
# -----------------------------------------------------------------------------
set -euo pipefail

MONGO_HOST="${MONGO_HOST:-mongo}"
MONGO_USER="${MONGO_USER:-root}"
OUT_FILE="${1:-data/partial_data.csv}"

AUTH_ARGS=(-u "${MONGO_USER}" --authenticationDatabase admin)
if [ -n "${MONGO_PASSWORD:-}" ]; then
  AUTH_ARGS+=(-p "${MONGO_PASSWORD}")
fi

mongoexport "${AUTH_ARGS[@]}" \
  --host "${MONGO_HOST}" \
  --db entertainment \
  --collection movies \
  --type=csv \
  --fields _id,title,year,rating,Director \
  --out "${OUT_FILE}"

# Verify the file instead of trusting "exported 100 records".
# A typo in --fields (e.g. "ratin") does NOT raise an error: it silently
# exports an empty column.
echo "--- header + first rows ---"
head -n 4 "${OUT_FILE}"
echo "--- line count (expected 101 = 1 header + 100 rows) ---"
wc -l < "${OUT_FILE}"
