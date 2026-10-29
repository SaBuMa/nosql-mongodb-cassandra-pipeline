"""
Unit tests for the validation layer.

Two kinds of tests:
  1. Small hand-made fixtures, to prove each function computes the right thing
     (including the exact bugs hit during the project).
  2. The real project data, to lock in every expected answer.

Run with:  pytest -v
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "validation"))

import validate as v  # noqa: E402

DATA = ROOT / "data"


# --------------------------------------------------------------------------- #
# Fixture data: 4 tiny movies, easy to check by hand
# --------------------------------------------------------------------------- #
@pytest.fixture
def tiny():
    return [
        {"_id": "1", "year": 2016, "Votes": 100, "rating": "G"},
        {"_id": "2", "year": 2016, "Votes": 300, "rating": "unrated"},
        {"_id": "3", "year": 2007, "Votes": 160, "rating": "G"},
        {"_id": "4", "year": 1999, "Votes": 225, "rating": "unrated"},
    ]


def test_top_year_counts_documents_not_year_values(tiny):
    # The $sum: "$year" bug would give 2016 + 2016 = 4032, not 2.
    assert v.top_year(tiny) == (2016, 2)


def test_count_after_excludes_the_boundary_year(tiny):
    # "after 1999" -> $gt, so 1999 itself is NOT counted
    assert v.count_after(tiny, 1999) == 3


def test_avg_votes_for_one_year(tiny):
    assert v.avg_votes(tiny, 2016) == 200.0


def test_avg_votes_for_missing_year_is_none(tiny):
    # Mirrors MongoDB: $avg over nothing returns null, not an error
    assert v.avg_votes(tiny, 1900) is None


def test_count_rating_is_exact_match(tiny):
    assert v.count_rating(tiny, "G") == 2
    assert v.count_rating(tiny, "g") == 0  # values are case-sensitive


# --------------------------------------------------------------------------- #
# Real project data: every expected answer
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def movies():
    return v.load_movies(DATA / "movies.json")


@pytest.fixture(scope="module")
def rows():
    return v.load_csv(DATA / "partial_data.csv")


def test_task1_documents(movies):
    assert len(movies) == 100


def test_task2_top_year(movies):
    assert v.top_year(movies) == (2016, 73)


def test_task3_after_1999(movies):
    assert v.count_after(movies, 1999) == 99


def test_task4_avg_votes_2007(movies):
    assert v.avg_votes(movies, 2007) == pytest.approx(192.5)


def test_task5_csv_has_expected_columns(rows):
    assert list(rows[0].keys()) == v.CSV_FIELDS
    assert len(rows) == 100


def test_task10_rated_g(rows):
    assert v.count_rating(rows, "G") == 32


def test_reconciliation_all_pass(movies, rows):
    failed = [c.name for c in v.reconcile(movies, rows) if not c.passed]
    assert failed == []


def test_csv_loses_types(rows):
    # In MongoDB _id is the string '1'; in the CSV everything is text anyway
    assert all(isinstance(value, str) for value in rows[0].values())


# --------------------------------------------------------------------------- #
# Data quality profile: the documented findings stay true
# --------------------------------------------------------------------------- #
def test_quality_findings(movies):
    q = v.profile(movies)
    assert "Runtime (Minutes)" in q["fields_not_snake_case"]
    assert "Director" in q["fields_not_snake_case"]
    assert q["numeric_fields_with_empty_strings"] == {"Revenue (Millions)": 9, "Metascore": 6}
    assert q["multi_value_fields_as_text"] == ["genre", "Actors"]
    assert q["docs_with_id_replace_corruption"] == 35
    assert q["id_type"] == ["str"]
    assert q["years_before_2000"] == [("32", "Top Dog", 1978)]
    assert q["docs_behind_2007_average"] == 2


def test_main_exit_code_is_zero():
    assert v.main(["--data-dir", str(DATA)]) == 0
