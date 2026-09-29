"""DataGuard Flask API."""
import io

from flask import Flask, Response, jsonify, request

from app.data_quality import analyze, clean, read_csv, validate

APP_TITLE = "DataGuard: Automated CI/CD Pipeline for a Containerized CSV Data Quality Service"
SERVICE_NAME = "dataguard"

app = Flask(__name__)


def _load_request_csv():
    """Accept either a multipart upload named `file` or a raw CSV request body."""
    if "file" in request.files:
        return read_csv(request.files["file"])
    body = request.get_data()
    if not body:
        return None
    return read_csv(io.BytesIO(body))


def _with_csv(handler):
    try:
        df = _load_request_csv()
    except Exception as exc:  # malformed CSV
        return jsonify({"error": f"could not parse CSV: {exc}"}), 400
    if df is None:
        return jsonify({"error": "no CSV provided; upload a 'file' field or send CSV as the body"}), 400
    return handler(df)


@app.get("/")
def index():
    return jsonify({
        "service": SERVICE_NAME,
        "title": APP_TITLE,
        "endpoints": {
            "GET /health": "liveness check",
            "POST /validate": "report data-quality issues",
            "POST /clean": "return cleaned CSV",
            "POST /analyze": "clean then return summary insights",
        },
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME}), 200


@app.post("/validate")
def validate_route():
    return _with_csv(lambda df: jsonify(validate(df)))


@app.post("/clean")
def clean_route():
    return _with_csv(lambda df: Response(clean(df).to_csv(index=False), mimetype="text/csv"))


@app.post("/analyze")
def analyze_route():
    return _with_csv(lambda df: jsonify(analyze(clean(df))))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
