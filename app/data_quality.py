"""Core CSV data-quality logic: validate, clean and analyze."""
import re

import pandas as pd

EXPECTED_COLUMNS = ["id", "name", "email", "age", "signup_date", "salary"]
NUMERIC_COLUMNS = ["id", "age", "salary"]
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AGE_MIN, AGE_MAX = 0, 120


def read_csv(source) -> pd.DataFrame:
    """Read a CSV as raw strings so validation sees values exactly as written."""
    return pd.read_csv(source, dtype=str, keep_default_na=True, skipinitialspace=False)


def _to_number(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"[$,]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")


def _parse_date(value):
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed
    return pd.NaT


def validate(df: pd.DataFrame) -> dict:
    """Return a report of data-quality issues. `valid` is True only if no issues are found."""
    issues = []

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        issues.append({"type": "missing_columns", "columns": missing_cols})
        return {"valid": False, "row_count": len(df), "issues": issues}

    for col in EXPECTED_COLUMNS:
        stripped = df[col].astype("string").str.strip()
        n_missing = int((df[col].isna() | (stripped == "")).sum())
        if n_missing:
            issues.append({"type": "missing_values", "column": col, "count": n_missing})

        n_whitespace = int((df[col].notna() & (df[col] != stripped)).sum())
        if n_whitespace:
            issues.append({"type": "extra_whitespace", "column": col, "count": n_whitespace})

    n_dup_rows = int(df.duplicated().sum())
    if n_dup_rows:
        issues.append({"type": "duplicate_rows", "count": n_dup_rows})

    ids = df["id"].dropna()
    n_dup_ids = int(ids.duplicated().sum())
    if n_dup_ids:
        issues.append({"type": "duplicate_ids", "count": n_dup_ids})

    for col in NUMERIC_COLUMNS:
        present = df[col].dropna()
        present = present[present.str.strip() != ""]
        n_bad = int(pd.to_numeric(present.str.strip(), errors="coerce").isna().sum())
        if n_bad:
            issues.append({"type": "type_mismatch", "column": col, "expected": "numeric", "count": n_bad})

    ages = pd.to_numeric(df["age"], errors="coerce").dropna()
    n_out_of_range = int(((ages < AGE_MIN) | (ages > AGE_MAX)).sum())
    if n_out_of_range:
        issues.append({"type": "out_of_range", "column": "age", "count": n_out_of_range})

    emails = df["email"].dropna().str.strip()
    n_bad_email = int((~emails.str.match(EMAIL_RE)).sum())
    if n_bad_email:
        issues.append({"type": "invalid_format", "column": "email", "count": n_bad_email})

    dates = df["signup_date"].dropna().str.strip()
    n_bad_date = int((~dates.str.match(ISO_DATE_RE)).sum())
    if n_bad_date:
        issues.append({"type": "invalid_format", "column": "signup_date", "expected": "YYYY-MM-DD", "count": n_bad_date})

    return {"valid": not issues, "row_count": len(df), "issues": issues}


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned copy of the data that satisfies `validate`."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[EXPECTED_COLUMNS]

    # Normalise text: trim whitespace everywhere, blank strings become missing.
    for col in EXPECTED_COLUMNS:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)

    df["id"] = _to_number(df["id"])
    df["name"] = df["name"].str.title()
    df["email"] = df["email"].str.lower()
    df.loc[~df["email"].fillna("").str.match(EMAIL_RE), "email"] = pd.NA

    age = _to_number(df["age"])
    age[(age < AGE_MIN) | (age > AGE_MAX)] = pd.NA
    df["age"] = age

    df["signup_date"] = df["signup_date"].map(_parse_date)
    df["salary"] = _to_number(df["salary"])

    # Rows without an id, valid email or parseable date are unusable, so they are dropped.
    df = df.dropna(subset=["id", "email", "signup_date"])
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset=["id"], keep="first")

    # Fill remaining numeric gaps with the column median.
    df["age"] = df["age"].fillna(df["age"].median()).round()
    df["salary"] = df["salary"].fillna(df["salary"].median()).round(2)
    df["name"] = df["name"].fillna("Unknown")

    df["id"] = df["id"].astype("int64")
    df["age"] = df["age"].astype("int64")
    df["name"] = df["name"].astype(object)
    df["email"] = df["email"].astype(object)
    df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.strftime("%Y-%m-%d")
    df["salary"] = df["salary"].astype("float64")

    return df.sort_values("id").reset_index(drop=True)


def analyze(df: pd.DataFrame) -> dict:
    """Summary insights for a (preferably cleaned) dataset."""
    summary = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "missing_values": {c: int(v) for c, v in df.isna().sum().items()},
        "numeric_summary": {},
    }
    for col in ("age", "salary"):
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(values):
                summary["numeric_summary"][col] = {
                    "mean": round(float(values.mean()), 2),
                    "median": round(float(values.median()), 2),
                    "min": round(float(values.min()), 2),
                    "max": round(float(values.max()), 2),
                }
    return summary
