"""Minimal HTTP server that serves the ONNX model file and a version string.
Endpoints:
  GET /model          → returns fire_detection.onnx binary
  GET /version        → returns plain-text version string (md5 of file)
  GET /health         → 200
"""

import hashlib
import os
from pathlib import Path
from flask import Flask, send_file, Response

app = Flask(__name__)
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/models"))
MODEL_FILE = MODEL_DIR / "fire_detection.onnx"


def _md5() -> str:
    if not MODEL_FILE.exists():
        return "no-model"
    h = hashlib.md5()
    with open(MODEL_FILE, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@app.route("/model")
def get_model():
    if not MODEL_FILE.exists():
        return Response("model not found", status=404)
    return send_file(MODEL_FILE, mimetype="application/octet-stream")


@app.route("/version")
def get_version():
    return Response(_md5(), mimetype="text/plain")


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
