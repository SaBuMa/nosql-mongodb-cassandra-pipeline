"""
Independent validation layer for the MongoDB -> CSV -> Cassandra project.

It recomputes every project answer directly from the source files with plain
Python (no database involved), reconciles the exported CSV against the source
JSON, and profiles the known data quality issues.

If the database queries and this script agree, the answers are trustworthy:
two independent methods, one result.

Usage:
    python validation/validate.py
    python validation/validate.py --data-dir data --summary report.md

Exit code 0 = all checks passed, 1 = at least one check failed.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Expected results, as returned by MongoDB 4.4 and Cassandra in the lab.
EXPECTED = {
    "documents_imported": 100,
    "top_year": 2016,
    "top_year_count": 73,
    "movies_after_1999": 99,
    "avg_votes_2007": 192.5,
    "csv_rows_exported": 100,
    "rated_g_count": 32,
}

CSV_FIELDS = ["_id", "title", "year", "rating", "Director"]
NUMERIC_FIELDS = ["year", "Runtime (Minutes)", "Votes", "Revenue (Millions)", "Metascore"]
MULTI_VALUE_FIELDS = ["genre", "Actors"]
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class Check:
    """One validation check: what was expected, what was found."""

    section: str
    name: str
    expected: object
    actual: object

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_movies(path: Path) -> list[dict]:
    """Load the newline-delimited JSON file (one document per line)."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_csv(path: Path) -> list[dict]:
    """Load the exported CSV. Every value comes back as text: CSV has no types."""
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# Project answers, recomputed in Python
# --------------------------------------------------------------------------- #
def movies_per_year(movies: list[dict]) -> Counter:
    """Equivalent of {$group: {_id: "$year", movie_count: {$sum: 1}}}."""
    return Counter(m["year"] for m in movies)


def top_year(movies: list[dict]) -> tuple[int, int]:
    """Task 2: the year with the most movies, and how many."""
    year, count = movies_per_year(movies).most_common(1)[0]
    return year, count


def count_after(movies: list[dict], year: int) -> int:
    """Task 3: movies with year strictly greater than `year` ($gt)."""
    return sum(1 for m in movies if m["year"] > year)


def avg_votes(movies: list[dict], year: int) -> float | None:
    """Task 4: average Votes for one year ($match + $group + $avg)."""
    votes = [m["Votes"] for m in movies if m["year"] == year]
    return sum(votes) / len(votes) if votes else None


def count_rating(rows: list[dict], rating: str) -> int:
    """Task 10: rows with an exact rating value."""
    return sum(1 for r in rows if r.get("rating") == rating)


# --------------------------------------------------------------------------- #
# Reconciliation: does the CSV faithfully represent the JSON?
# --------------------------------------------------------------------------- #
def reconcile(movies: list[dict], rows: list[dict]) -> list[Check]:
    source = {m["_id"]: m for m in movies}
    exported = {r["_id"]: r for r in rows}

    mismatches = []
    for _id, row in exported.items():
        doc = source.get(_id)
        if doc is None:
            continue
        for field in CSV_FIELDS[1:]:
            # CSV stores text, so compare the text form of the source value
            if str(doc[field]) != row.get(field):
                mismatches.append((_id, field))

    return [
        Check("Reconciliation", "CSV header matches exported fields", CSV_FIELDS, list(rows[0].keys()) if rows else []),
        Check("Reconciliation", "Row count JSON vs CSV", len(movies), len(rows)),
        Check("Reconciliation", "Duplicate ids in CSV", 0, len(rows) - len(exported)),
        Check("Reconciliation", "Ids missing from CSV", [], sorted(set(source) - set(exported), key=int)),
        Check("Reconciliation", "Unexpected ids in CSV", [], sorted(set(exported) - set(source), key=int)),
        Check(
            "Reconciliation",
            "Field values that differ" + (f" (first: {mismatches[:3]})" if mismatches else ""),
            0,
            len(mismatches),
        ),
        Check("Reconciliation", "Rated 'G': JSON vs CSV", count_rating(movies, "G"), count_rating(rows, "G")),
    ]


# --------------------------------------------------------------------------- #
# Data quality profile
# --------------------------------------------------------------------------- #
def profile(movies: list[dict]) -> dict:
    """Measure the data quality issues documented in docs/data_quality_report.md."""
    keys = sorted({k for m in movies for k in m})

    empty_strings = {
        f: sum(1 for m in movies if m.get(f) == "") for f in NUMERIC_FIELDS
    }

    corrupted_docs = [
        m["_id"]
        for m in movies
        if any(isinstance(v, str) and "_id" in v for k, v in m.items() if k != "_id")
    ]
    corrupted_occurrences = sum(
        v.count("_id") for m in movies for k, v in m.items() if k != "_id" and isinstance(v, str)
    )

    return {
        "fields_total": len(keys),
        "fields_not_snake_case": [k for k in keys if not SAFE_NAME.match(k)],
        "numeric_fields_with_empty_strings": {f: n for f, n in empty_strings.items() if n},
        "multi_value_fields_as_text": [
            # always a string (never an array), and comma-separated in practice
            f for f in MULTI_VALUE_FIELDS
            if all(isinstance(m[f], str) for m in movies) and any("," in m[f] for m in movies)
        ],
        "docs_with_id_replace_corruption": len(corrupted_docs),
        "id_replace_occurrences": corrupted_occurrences,
        "id_type": sorted({type(m["_id"]).__name__ for m in movies}),
        "years_before_2000": [(m["_id"], m["title"], m["year"]) for m in movies if m["year"] < 2000],
        "docs_behind_2007_average": len([m for m in movies if m["year"] == 2007]),
    }


# --------------------------------------------------------------------------- #
# Run everything
# --------------------------------------------------------------------------- #
def run_checks(data_dir: Path) -> tuple[list[Check], dict]:
    movies = load_movies(data_dir / "movies.json")
    rows = load_csv(data_dir / "partial_data.csv")

    year, year_count = top_year(movies)
    checks = [
        Check("MongoDB", "Task 1 - documents imported", EXPECTED["documents_imported"], len(movies)),
        Check("MongoDB", "Task 2 - year with most movies", EXPECTED["top_year"], year),
        Check("MongoDB", "Task 2 - movies in that year", EXPECTED["top_year_count"], year_count),
        Check("MongoDB", "Task 3 - movies after 1999", EXPECTED["movies_after_1999"], count_after(movies, 1999)),
        Check("MongoDB", "Task 4 - average votes in 2007", EXPECTED["avg_votes_2007"], avg_votes(movies, 2007)),
        Check("Cassandra", "Task 5/7 - CSV rows exported and imported", EXPECTED["csv_rows_exported"], len(rows)),
        Check("Cassandra", "Task 8 - row count", EXPECTED["documents_imported"], len(rows)),
        Check("Cassandra", "Task 10 - movies rated 'G'", EXPECTED["rated_g_count"], count_rating(rows, "G")),
    ]
    checks += reconcile(movies, rows)
    return checks, profile(movies)


def render_markdown(checks: list[Check], quality: dict) -> str:
    passed = sum(c.passed for c in checks)
    lines = [
        "## Validation report",
        "",
        f"**{passed}/{len(checks)} checks passed**",
        "",
        "| Section | Check | Expected | Actual | Result |",
        "|---|---|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c.section} | {c.name} | `{c.expected}` | `{c.actual}` | {'✅' if c.passed else '❌'} |")

    lines += ["", "## Data quality profile", "", "| Finding | Value |", "|---|---|"]
    for key, value in quality.items():
        lines.append(f"| {key} | `{value}` |")
    return "\n".join(lines) + "\n"


def print_console(checks: list[Check], quality: dict) -> None:
    print("=" * 78)
    print(" VALIDATION REPORT")
    print("=" * 78)
    section = None
    for c in checks:
        if c.section != section:
            section = c.section
            print(f"\n[{section}]")
        mark = "PASS" if c.passed else "FAIL"
        print(f"  {mark}  {c.name:<45} expected={c.expected!r:<8} actual={c.actual!r}")

    print("\n[Data quality profile]")
    for key, value in quality.items():
        print(f"  - {key}: {value}")

    passed = sum(c.passed for c in checks)
    print("\n" + "=" * 78)
    print(f" {passed}/{len(checks)} checks passed")
    print("=" * 78)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    parser.add_argument("--summary", type=Path, help="Append a Markdown report to this file (e.g. $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)

    checks, quality = run_checks(args.data_dir)
    print_console(checks, quality)

    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write(render_markdown(checks, quality))

    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
