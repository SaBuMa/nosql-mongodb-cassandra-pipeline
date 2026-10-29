# MongoDB vs Cassandra: Concepts and Design Decisions

What this project showed about how the two databases think, with the decisions made along the way.

## At a glance

| | MongoDB | Cassandra |
|---|---|---|
| Data model | Documents (JSON-like), flexible schema | Tables with typed columns, schema up front |
| Create a database | On the fly (`use entertainment`) | Explicit keyspace **with replication settings** |
| Types | Whatever each document contains | Declared per column; values must fit |
| Query style | Query any field any way (aggregation pipeline) | Design tables around the queries you will run |
| Filter on a non-key field | Works (full scan, silently) | Refused unless indexed or `ALLOW FILTERING` |
| Row order | Insertion / `_id` order | Token order (hash of the partition key) |
| Counting everything | Cheap on small collections | `COUNT(*)` scans every node; warns |
| Shell | `mongosh` (JavaScript) | `cqlsh` (CQL, SQL-like) |

## 1. Replication: decided at creation

**Analogy:** a keyspace is an important contract. You must tell the office how many photocopies to keep and in which filing cabinets.

```
Production cluster (RF = 3)        This lab (1 node)
├── Node A [copy 1]                └── Node A [copy 1]
├── Node B [copy 2]
└── Node C [copy 3]
```

**Decision:** `SimpleStrategy`, `replication_factor = 1`.
- Replication factor must be ≤ number of nodes. RF 3 on one node only produced a warning: no real copies exist, and QUORUM operations would fail.
- Production would use `NetworkTopologyStrategy` with RF 3 per datacenter.
- `ALTER KEYSPACE ... WITH replication = {...}` replaces the **whole** map, so the `class` must always be included.

## 2. Partitioning: why rows come back "shuffled"

```
SELECT * FROM movies LIMIT 5;   →  ids 6, 90, 46, 55, 81
```

**Analogy:** a coat check with several rooms. Your ticket number (the primary key) goes through a scrambling machine (a hash function) that outputs a room and shelf. The same ticket always gives the same shelf, so lookups are instant, but walking the shelves shows coats in scrambled order.

```
id "6"  ──hash──► token -8… ┐
id "90" ──hash──► token -7… │  stored in TOKEN order
id "46" ──hash──► token -2… │
id "55" ──hash──► token  1… │
id "81" ──hash──► token  6… ┘

        Node A          Node B          Node C
   [ low tokens ]  [ mid tokens ]  [ high tokens ]
```

Why on purpose: sequential ids would send every new write to the same node (a hot spot). Hashing spreads data and load evenly.

Consequences:
- `WHERE id = '55'` → hash → straight to the right node. ⚡
- Sorting the whole table, or filtering by another column, is not what Cassandra is built for.

## 3. Secondary index and `ALLOW FILTERING`

Before the index, `WHERE rating = 'G'` was refused: Cassandra would have to scan everything and makes you opt in with `ALLOW FILTERING`. MongoDB runs the same scan without a word.

`CREATE INDEX rating_index ON movies (rating)` adds a **local** index on each node:

```
Node A: "G" → its own rows   |  "unrated" → its own rows
Node B: "G" → its own rows   |  "unrated" → its own rows
```

The query still asks every node (hence `Aggregation query used without partition key`), just faster once there. For heavy production queries, the usual pattern is a separate table partitioned by the query's key (e.g. `movies_by_rating`).

## 4. Types across the pipeline

```
MongoDB  _id: '1' (string), year: 2016 (int)
   │ mongoexport
   ▼
CSV      1, 2016            ← just characters, no types
   │ COPY
   ▼
Cassandra id text, year text  ← types decided again, by the table
```

**Decision:** all Cassandra columns are `text`, as the brief required. Trade-off: `year > '1999'` would compare in dictionary order, not numerically. A production table would use `int` for `year` after cleaning the empty strings.

## 5. Identifiers

| Rule | MongoDB | Cassandra (CQL) |
|---|---|---|
| Names with spaces / parentheses | `{"Runtime (Minutes)": ...}` | Must be `"double quoted"` every time |
| Leading underscore (`_id`) | Normal (it's the primary key) | Unquoted names must start with a letter |
| Case | Case-sensitive (`Votes` ≠ `votes`) | Unquoted names are lowercased |
| Single quotes | — | Always a **text value**, never a name |

**Decision:** the Cassandra key is `id`, not `"_id"`, to avoid carrying double quotes in every query.

## 6. `COPY` maps by position

`COPY movies (id, title, year, rating, director) FROM 'partial_data.csv' WITH HEADER = TRUE` **skips** the header and maps the 1st CSV value to the 1st listed column, and so on. The CSV header names (`_id`, `Director`) are never matched by name, so the column list must follow the CSV order.

## 7. Counting at scale

`SELECT COUNT(*)` is instant on 100 rows but scans every partition on every node of a large table and can time out. Alternatives: `nodetool tablestats` estimates, a counter maintained on write, or a batch job (Spark).

## 8. Idempotency

| Operation | Run twice | Why |
|---|---|---|
| `mongoimport` with explicit `_id` | Second run rejected (`E11000` duplicate key) | `_id` must be unique |
| `mongoimport` without `_id` | **200 documents** silently | New ObjectIds every run |
| `CREATE ... IF NOT EXISTS` | No-op | Explicitly idempotent |
| Cassandra `COPY` of the same rows | Same 100 rows | Writes with the same primary key overwrite (upsert) |
