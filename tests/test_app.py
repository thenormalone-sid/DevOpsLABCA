"""API and unit tests for the DataGuard service."""
import io
from pathlib import Path

import pytest

from app.data_quality import analyze, clean, read_csv
from app.main import APP_TITLE, app

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _upload(path):
    return {"file": (io.BytesIO(path.read_bytes()), path.name)}


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "service": "dataguard"}


def test_index_shows_title(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == APP_TITLE


def test_validate_endpoint_flags_messy_file(client):
    resp = client.post("/validate", data=_upload(DATA_DIR / "messy_sample.csv"),
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["valid"] is False


def test_validate_endpoint_accepts_raw_body(client):
    resp = client.post("/validate", data=(DATA_DIR / "clean_sample.csv").read_bytes(),
                       content_type="text/csv")
    assert resp.status_code == 200
    assert resp.get_json()["valid"] is True


def test_clean_endpoint_returns_csv(client):
    resp = client.post("/clean", data=_upload(DATA_DIR / "messy_sample.csv"),
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert resp.data.decode().splitlines()[0] == "id,name,email,age,signup_date,salary"


def test_analyze_endpoint_returns_summary(client):
    resp = client.post("/analyze", data=_upload(DATA_DIR / "clean_sample.csv"),
                       content_type="multipart/form-data")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["row_count"] == 10
    assert body["numeric_summary"]["age"]["min"] == 23


def test_missing_csv_returns_400(client):
    assert client.post("/validate").status_code == 400


def test_clean_is_idempotent():
    once = clean(read_csv(DATA_DIR / "messy_sample.csv"))
    twice = clean(read_csv(io.StringIO(once.to_csv(index=False))))
    assert once.equals(twice)


def test_analyze_counts_missing_values():
    df = read_csv(io.StringIO("id,age,salary\n1,,100\n2,30,\n"))
    summary = analyze(df)
    assert summary["missing_values"] == {"id": 0, "age": 1, "salary": 1}
