from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from rockburst_lab.orchestrator import RockburstLabOrchestrator


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_data"


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    orchestrator = RockburstLabOrchestrator(
        default_microseismic_path=SAMPLE_DIR / "microseismic.csv",
        default_tbm_path=SAMPLE_DIR / "tbm.csv",
        default_geology_path=SAMPLE_DIR / "geology.json",
    )

    @app.get("/api/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "service": "rockburst-agent-lab"}), 200

    @app.get("/api/lab/run")
    def run_default_lab() -> tuple[Any, int]:
        return jsonify(orchestrator.run()), 200

    @app.post("/api/lab/run")
    def run_custom_lab() -> tuple[Any, int]:
        payload = request.get_json(silent=True) or {}
        result = orchestrator.run(
            microseismic_path=payload.get("microseismic_path"),
            tbm_path=payload.get("tbm_path"),
            geology_path=payload.get("geology_path"),
        )
        return jsonify(result), 200

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
