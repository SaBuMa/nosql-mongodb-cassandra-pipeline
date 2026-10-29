# Validation Layer and CI, Explained

This document explains **what** the Python validation and the GitHub Actions CI do, **why** they exist, and **how** to run, read and break them on purpose.

---

## 1. The big idea: a second witness

**Analogy:** imagine an accountant closing the books. The accounting software says the total is $192.50. A good accountant doesn't just trust it: they grab a calculator and add the receipts by hand. If both numbers agree, the result is trustworthy. If they don't, something is wrong in one of them, and now you know to look.

In this project:

```
                 ┌─────────────────────────────┐
                 │        movies.json          │
                 └──────────────┬──────────────┘
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
 ┌──────────────────────┐                  ┌──────────────────────┐
 │  WITNESS 1: databases│                  │  WITNESS 2: Python    │
 │  MongoDB aggregations│                  │  validation/validate.py│
 │  Cassandra CQL       │                  │  (no database at all) │
 └──────────┬───────────┘                  └──────────┬───────────┘
            │   73 · 99 · 192.5 · 32                  │   73 · 99 · 192.5 · 32
            └──────────────────┬──────────────────────┘
                               ▼
                       Same answers? ✅
```

The two methods share **nothing** except the input file. A bug in one (like `$sum: "$year"` adding years instead of counting) can't hide, because the other witness disagrees.

---

## 2. What `validate.py` checks

It runs three groups of checks and prints a report.

### 2.1 Project answers (8 checks)

Each task is recomputed in plain Python, mirroring the database query:

| Task | MongoDB / CQL | Python equivalent |
|---|---|---|
| 1 | `countDocuments()` → 100 | `len(movies)` |
| 2 | `$group` by year + `$sum: 1` → 2016 (73) | `Counter(m["year"] ...)`.most_common(1) |
| 3 | `{year: {$gt: 1999}}` → 99 | `sum(1 for m if m["year"] > 1999)` |
| 4 | `$match` 2007 + `$avg: "$Votes"` → 192.5 | average of `Votes` where year == 2007 |
| 5/7 | `mongoexport` → `COPY` → 100 rows | rows in `partial_data.csv` |
| 8 | `SELECT COUNT(*)` → 100 | rows in the CSV |
| 10 | `WHERE rating = 'G'` → 32 | rows with rating == "G" |

### 2.2 Reconciliation (7 checks)

**Analogy:** a moving company. Before the truck leaves, you list every box. When it arrives, you check the list again: same number of boxes, none missing, none extra, nothing broken inside.

```
movies.json (100 docs)            partial_data.csv (100 rows)
┌────┬──────────────┐             ┌────┬──────────────┐
│ 1  │ Guardians... │ ── same? ──►│ 1  │ Guardians... │
│ 2  │ Prometheus   │ ── same? ──►│ 2  │ Prometheus   │
│ …  │ …            │             │ …  │ …            │
└────┴──────────────┘             └────┴──────────────┘
```

It checks:
1. The CSV header is exactly `_id, title, year, rating, Director` (catches the `ratin` typo).
2. Same row count on both sides.
3. No duplicate ids in the CSV.
4. No ids missing from the CSV.
5. No unexpected ids in the CSV.
6. Every exported field value matches the source, compared as text (CSV has no types).
7. The `G` count is the same in the JSON and the CSV.

### 2.3 Data quality profile (informational)

Measures the issues documented in [`data_quality_report.md`](data_quality_report.md): unsafe field names, empty strings in numeric fields, multi-value text fields, the `_id` replace corruption, suspicious years, and how many documents the 2007 average is built on.

These are **reported**, not failed: the data is the course's data, and the checks must pass with it. The unit tests, however, lock in the exact counts, so the report can never silently go out of date.

---

## 3. The unit tests (`tests/test_validate.py`)

**Analogy:** before trusting a calculator to check the accountant, you test the calculator with sums you already know: 2 + 2 = 4.

The tests use two kinds of data:

```
┌────────────────────────────────┐   ┌────────────────────────────────┐
│ Tiny hand-made fixture (4 rows)│   │ The real project data          │
│ answers checkable by eye       │   │ locks in every expected answer │
│                                │   │                                │
│ • counts docs, not years       │   │ • 100 docs, 2016 → 73          │
│   (the $sum: "$year" bug)      │   │ • 99 after 1999                │
│ • "after 1999" excludes 1999   │   │ • 192.5 average in 2007        │
│ • $avg over nothing → None     │   │ • 32 rated G                   │
│ • "G" ≠ "g" (case-sensitive)   │   │ • reconciliation all pass      │
│                                │   │ • quality findings unchanged   │
└────────────────────────────────┘   └────────────────────────────────┘
```

Several tests encode the **real mistakes made during the project**, so they can never come back unnoticed.

---

## 4. CI: the robot that never forgets

**Analogy:** a security guard at the door of the repository. Every time anyone pushes a change, the guard runs the full checklist automatically. You don't have to remember to run it, and nobody can skip it.

CI means **Continuous Integration**: every change is automatically integrated and verified.

The workflow file is [`.github/workflows/validate.yml`](../.github/workflows/validate.yml):

```
git push / pull request / manual run
              │
              ▼
┌──────────────────────────────────────────────┐
│  GitHub spins up a fresh Ubuntu machine       │
│                                               │
│  1. checkout        → copy the repo           │
│  2. setup-python    → install Python 3.12     │
│  3. pip install     → install pytest          │
│  4. pytest -v       → run the 15 unit tests   │
│  5. validate.py     → run the 15 checks and   │
│                       write the report to the │
│                       job summary page        │
└──────────────────────┬───────────────────────┘
                       ▼
          ✅ green badge   or   ❌ red badge
```

**Triggers** (the `on:` block):
- `push` to `main`: every commit you upload
- `pull_request`: every proposed change
- `workflow_dispatch`: a manual "Run workflow" button in the Actions tab

**Fresh machine every time:** the job starts from a clean computer, so it proves the project works anywhere, not just "on my machine."

---

## 5. How to run it locally

From the repository root:

```bash
pip install -r requirements.txt     # only pytest; validate.py needs nothing else
pytest -v                           # 15 tests
python validation/validate.py       # 15 checks + quality profile
echo $?                             # 0 = all passed, 1 = something failed
```

Optional Markdown report:

```bash
python validation/validate.py --summary report.md
```

---

## 6. How to read the results on GitHub

1. Open the repository → **Actions** tab.
2. Click the latest **Validate data and answers** run.
3. The **Summary** page shows the Markdown report: a table of every check with ✅ / ❌, plus the data quality profile.
4. Click the **validate** job to see each step's console output (`pytest -v` lists every test by name).

The badge at the top of the README always shows the status of the latest run on `main`.

---

## 7. Break it on purpose (the best way to learn it)

Try these locally, see the failure, then undo the change:

| Experiment | What fails | Lesson |
|---|---|---|
| Change `ratin` back into the CSV header | Reconciliation: header check | Typos in `--fields` give empty columns, not errors |
| Delete one row from `partial_data.csv` | Row count, missing ids, Task 10 maybe | Reconciliation catches data lost in transit |
| In `top_year`, count `m["year"]` values instead of 1 | Task 2 + unit test | The `$sum: "$year"` bug |
| Change `>` to `>=` in `count_after` | Task 3 + boundary test | `$gt` vs `$gte` |
| Edit a title in the CSV | "Field values that differ" | Silent corruption between systems |

If you push a broken change, the CI badge turns red and GitHub emails you. That's the guard doing its job.

---

## 8. Why this matters for data engineering

- **Reconciliation** (counts and values match at both ends) is standard practice after every data migration or pipeline run.
- **Independent verification** catches logic bugs that "the query ran without errors" never will.
- **Automated checks in CI** turn one-time verification into a permanent safety net.
- The same ideas scale up to tools like Great Expectations, dbt tests and Soda in production pipelines.
