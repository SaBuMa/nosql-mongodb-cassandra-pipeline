-- -----------------------------------------------------------------------------
-- Task 6 - Create the keyspace "entertainment"
--
-- Run with:  cqlsh -f scripts/cassandra/01_create_keyspace.cql
--
-- Unlike MongoDB (databases are created on the fly), Cassandra needs the
-- replication settings up front: how many copies of each row, and how to
-- place them across nodes.
--
-- Decision: SimpleStrategy + replication_factor 1
--   * The lab cluster has ONE node; replication factor must be <= nodes.
--   * RF 3 on one node only triggers a warning:
--     "Your replication factor 3 for keyspace entertainment is higher than
--      the number of nodes 1"  -> it "works", but no real copies exist and
--      QUORUM operations would fail.
--   * In production: NetworkTopologyStrategy with RF 3 per datacenter.
-- -----------------------------------------------------------------------------

CREATE KEYSPACE IF NOT EXISTS entertainment
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

-- If the keyspace already exists with the wrong settings, ALTER it.
-- ALTER replaces the WHOLE replication map, so the class must be included.
ALTER KEYSPACE entertainment
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

DESCRIBE KEYSPACE entertainment;
-- CREATE KEYSPACE entertainment WITH replication =
--   {'class': 'SimpleStrategy', 'replication_factor': '1'}  AND durable_writes = true;
