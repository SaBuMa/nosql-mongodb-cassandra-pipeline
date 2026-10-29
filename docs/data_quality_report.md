# Data Quality Report: `movies.json`

> Profiled **before** loading, then tracked through every stage of the pipeline.
> All counts below are measured by [`validation/validate.py`](../validation/validate.py) and locked in by the unit tests, so this report cannot silently drift from the data.

## Summary

| # | Finding | Severity | Records affected | Hurts most in |
|---|---|---|---|---|
| 1 | Field names with spaces, parentheses and mixed case | Medium | 8 of 12 fields not lowercase snake_case | Cassandra |
| 2 | Numeric fields containing empty strings `""` | High | 9 `Revenue`, 6 `Metascore` | Aggregations, typed schemas |
| 3 | Multi-value fields stored as comma-separated text | Medium | `genre`, `Actors` (100 records) | Filtering by genre/actor |
| 4 | Global find-and-replace `id` → `_id` corrupted text | High | 35 records, 43 occurrences | Text search, joins by name |
| 5 | Semantically wrong values (`year`, `Votes`, `rating`) | High | e.g. records 32, 46, 76, 93 | Every answer built on them |
| 6 | `_id` stored as text, not a number | Low | 100 records | Sorting, lookups by number |

```
movies.json ──► MongoDB ──► partial_data.csv ──► Cassandra
     │             │               │                 │
     └──── issues 4 and 5 travel through EVERY stage untouched ────┘
```

Bad data does not fix itself in a pipeline: it gets copied everywhere. `Pirates of the Caribbean: On Stranger T_ides` was still corrupted when queried in Cassandra.

---

## 1. Field names that are hard to query

**Evidence**

```json
"Runtime (Minutes)": 121, "Revenue (Millions)": 333.13, "Director": "James Gunn", "year": 2014
```

- Spaces and parentheses: `Runtime (Minutes)`, `Revenue (Millions)`
- Mixed case: `title`, `year`, `rating` vs `Description`, `Director`, `Actors`, `Votes`, `Metascore`
- Leading underscore: `_id`

**Impact**
- MongoDB accepts any of these, quoted as JSON keys.
- In CQL, unquoted names must start with a letter and are lowercased. `Director` becomes `director`; `_id` and `Runtime (Minutes)` need double quotes forever.
- `$Votes` ≠ `$votes`: averaging a misspelled field returns `null`, with no error.

**Recommended fix:** normalize to `snake_case` at ingestion (`runtime_minutes`, `revenue_millions`, `director`, `movie_id`).

## 2. Numeric fields with empty strings

**Evidence**

```json
{"_id":"1", "Revenue (Millions)": 333.13, "Metascore": 76}
{"_id":"8", "Revenue (Millions)": "",     "Metascore": 71}
{"_id":"26","Revenue (Millions)": "",     "Metascore": ""}
```

| Field | Numbers | Empty strings |
|---|---|---|
| `Revenue (Millions)` | 91 | 9 |
| `Metascore` | 94 | 6 |

Four records (26, 40, 43 and 48) have both fields empty.

**Why it matters:** `""`, `null` and a missing field are three different things.

```
"Metascore": null   → explicit "no value"
"Metascore": ""     → an empty TEXT value   ← what this dataset uses
(no Metascore key)  → the field does not exist
```

- MongoDB stores mixed types without complaint, but sorting compares numbers and strings in separate groups, and `$avg` silently skips non-numeric values.
- A Cassandra `decimal` or `int` column would reject `""` on import.

**Recommended fix:** convert `""` to `null` (or drop the key) for numeric fields before loading.

## 3. Multi-value fields stored as text

**Evidence**

```json
"genre":  "Action,Adventure,Sci-Fi"
"Actors": "Chris Pratt, Vin Diesel, Bradley Cooper, Zoe Saldana"
```

To the database each value is **one string**, not three genres. Finding Sci-Fi movies needs a pattern match (`$regex`) instead of an exact or array match. Separators are also inconsistent: 42 `Actors` values have names glued without a space (`"Julian Barratt,Kenneth Branagh"`).

**Recommended fix:** split into arrays in MongoDB (`["Action", "Adventure", "Sci-Fi"]`, queryable with `$in` and indexable as multikey) and into `set<text>` columns in Cassandra; trim whitespace.

## 4. Over-broad find-and-replace: `id` → `_id`

**Evidence**

| Field | Example | Should be |
|---|---|---|
| `title` | `Suic_ide Squad`, `H_idden Figures`, `The Vo_id` | Suicide, Hidden, Void |
| `Director` | `R_idley Scott`, `Dav_id Fincher`, `Dav_id F_idel` | Ridley, David, Fidel |
| `Actors` | `Nicole K_idman`, `_idris Elba`, `Daisy R_idley` | Kidman, Idris, Ridley |
| `Description` | `k_idnapped`, `afra_id`, `_identify` | kidnapped, afraid, identify |

**35 records, 43 occurrences.** Affected fields: `Description` in 21 records, `title` in 7, `Director` in 5, `Actors` in 4 (some records are hit in more than one field).

**Root cause:** someone renamed the key `id` to `_id` (MongoDB's primary key) with a global text replace, which also hit every word containing the letters "id".

**Impact:** an exact search for `Ridley Scott` or `David Fincher` returns nothing.

**Recommended fix:** scope transformations to the structure, not the text: rename the **key** with a JSON-aware tool (`jq`, Python, `$rename`). To repair the current file: replace `_id` with `id` in every **value** except the `_id` key itself, then spot-check names like "_idris" → "Idris" (capitalization was lost).

## 5. Values that are the right type but wrong meaning

No schema or type check catches these. Only looking at the data does.

| Record | Title | Issue |
|---|---|---|
| 32 | Top Dog | `year: 1978`, but the plot, actors and Metascore match a 2016 film. It is the only movie before 2000, so it alone decides the Task 3 answer (99 instead of 100). |
| 46 | Pirates of the Caribbean: On Stranger Tides | `year: 2007` and only `Votes: 160`, despite $241M revenue. |
| 93 | The Help | `year: 2007` and only `Votes: 225`. |
| 76 | Pirates of the Caribbean: At World's End | `year: 2016` for an earlier sequel. |
| 34 | Deadpool | `rating: "G"` for an R-rated film. |

**Impact on the project answers:** the Task 4 average (192.5 votes in 2007) is computed from **only two documents**, records 46 and 93, both suspicious. The answer is correct for the data, and fragile in the real world.

**Recommended fix:** add range and plausibility checks (votes vs revenue, release year vs actor careers) and report how many records each aggregate is built on.

## 6. `_id` stored as text

`"_id": "1"` is the string `'1'`, not the number 1.

- `db.movies.find({_id: 1})` returns nothing; `{_id: "1"}` works.
- Sorting by `_id` gives dictionary order: `"1", "10", "100", "11", ...`.
- The CSV export erases the difference entirely (`1` is just characters), so the next system has to decide the type again. Cassandra stores it as `text` here.

**Upside:** because every document carries an explicit `_id`, re-running `mongoimport` is **idempotent**: duplicates are rejected with `E11000` instead of silently doubling the collection.
