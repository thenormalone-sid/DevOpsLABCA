"""Golden-file data-quality regression tests."""
import io
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_quality import clean, read_csv, validate

DATA_DIR = Path(__file__).parent / "data"
EXPECTED_DTYPES = {
    "id": "int64",
    "name": object,
    "email": object,
    "age": "int64",
    "signup_date": object,
    "salary": "float64",
}


def test_cleaning_messy_sample_matches_golden_output():
    cleaned = clean(read_csv(DATA_DIR / "messy_sample.csv"))
    expected = pd.read_csv(DATA_DIR / "expected_cleaned.csv", dtype=EXPECTED_DTYPES)
    assert_frame_equal(cleaned, expected)


def test_clean_sample_passes_validation():
    report = validate(read_csv(DATA_DIR / "clean_sample.csv"))
    assert report["valid"] is True
    assert report["issues"] == []


def test_messy_sample_is_flagged_by_validation():
    report = validate(read_csv(DATA_DIR / "messy_sample.csv"))
    assert report["valid"] is False
    issue_types = {issue["type"] for issue in report["issues"]}
    assert {
        "missing_values",
        "duplicate_rows",
        "duplicate_ids",
        "type_mismatch",
        "extra_whitespace",
        "invalid_format",
    } <= issue_types


def test_cleaned_output_passes_validation():
    cleaned = clean(read_csv(DATA_DIR / "messy_sample.csv"))
    reread = read_csv(io.StringIO(cleaned.to_csv(index=False)))
    assert validate(reread)["valid"] is True
