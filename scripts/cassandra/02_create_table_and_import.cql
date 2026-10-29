-- -----------------------------------------------------------------------------
-- Task 7 - Create table "movies" and import partial_data.csv
--
-- Run from the repository root with:
--   cqlsh -f scripts/cassandra/02_create_table_and_import.cql
--
-- Design decisions:
--   * All columns are text, as required by the project brief. Trade-off:
--     year as text compares in dictionary order, not numeric order.
--   * The column is "id", not "_id": unquoted CQL identifiers must start with
--     a letter. "_id" would need double quotes in EVERY future query
--     (single quotes mean a text value in CQL, not a name).
--   * Unquoted identifiers are lowercased, so "Director" in the CSV maps to
--     the column "director".
-- -----------------------------------------------------------------------------

USE entertainment;

CREATE TABLE IF NOT EXISTS movies (
    id       text PRIMARY KEY,
    title    text,
    year     text,
    rating   text,
    director text
);

-- COPY maps CSV values to columns by POSITION, not by header name.
-- HEADER = TRUE only skips the first line. The column list must follow the
-- CSV column order: _id, title, year, rating, Director.
COPY entertainment.movies (id, title, year, rating, director)
FROM 'data/partial_data.csv'
WITH DELIMITER = ',' AND HEADER = TRUE;
-- 100 rows imported from 1 files in 0.765 seconds (0 skipped).

-- Verify from the other side
SELECT COUNT(*) FROM entertainment.movies;      -- 100

-- Rows come back in TOKEN order (hash of the partition key), not id order
SELECT * FROM entertainment.movies LIMIT 5;
