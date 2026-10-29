-- -----------------------------------------------------------------------------
-- Tasks 8-10 - Count, secondary index, filtered count
--
-- Run with:  cqlsh -f scripts/cassandra/03_queries_and_index.cql
-- -----------------------------------------------------------------------------

-- Task 8 - Count the rows in the movies table
SELECT COUNT(*) FROM entertainment.movies;
-- count = 100
-- Fine for 100 rows. On large tables COUNT(*) scans every partition on every
-- node and can time out; use estimates (nodetool tablestats), a maintained
-- counter, or a batch job (e.g. Spark) instead.

-- Task 9 - Secondary index on rating
-- Without it, WHERE rating = 'G' is refused unless ALLOW FILTERING is added
-- (Cassandra makes you opt in to a full scan explicitly).
CREATE INDEX IF NOT EXISTS rating_index ON entertainment.movies (rating);

-- Task 10 - Count the movies rated 'G'
SELECT COUNT(*) FROM entertainment.movies WHERE rating = 'G';
-- count = 32
-- Warning: Aggregation query used without partition key
-- The index is LOCAL to each node, so the query still asks every node.
-- Reconciled with MongoDB: db.movies.countDocuments({rating: "G"}) -> 32
