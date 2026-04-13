from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from rockburst_lab.orchestrator import RockburstLabOrchestrator


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_data"

UPLOAD_EXTENSIONS = {
    "microseismic_file": {".csv", ".xlsx"},
    "tbm_file": {".csv", ".xlsx"},
    "geology_file": {".json"},
}


def _uploaded_target_path(tmp_path: Path, field_name: str, original_name: str) -> Path:
    suffix = Path(original_name).suffix.lower()
    allowed = UPLOAD_EXTENSIONS[field_name]
    if suffix not in allowed:
        allowed_text = "、".join(sorted(allowed))
        raise ValueError(f"{field_name} 仅支持 {allowed_text} 格式")
    return tmp_path / f"{field_name}{suffix}"


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
        if request.files:
            with TemporaryDirectory(prefix="rockburst-agent-lab-") as tmp_dir:
                tmp_path = Path(tmp_dir)
                uploaded_paths: dict[str, Path] = {}
                upload_map = {
                    "microseismic_file": "microseismic",
                    "tbm_file": "tbm",
                    "geology_file": "geology",
                }
                for field_name in upload_map:
                    storage = request.files.get(field_name)
                    if storage and storage.filename:
                        try:
                            target = _uploaded_target_path(tmp_path, field_name, storage.filename)
                        except ValueError as exc:
                            return jsonify({"error": str(exc)}), 400
                        storage.save(target)
                        uploaded_paths[field_name] = target

                try:
                    result = orchestrator.run(
                        microseismic_path=uploaded_paths.get("microseismic_file"),
                        tbm_path=uploaded_paths.get("tbm_file"),
                        geology_path=uploaded_paths.get("geology_file"),
                    )
                except Exception as exc:
                    return jsonify({"error": f"上传数据解析失败：{exc}"}), 400

                result["upload"] = {
                    "mode": "multipart",
                    "received": sorted(uploaded_paths.keys()),
                }
                return jsonify(result), 200

        payload = request.get_json(silent=True) or {}
        try:
            result = orchestrator.run(
                microseismic_path=payload.get("microseismic_path"),
                tbm_path=payload.get("tbm_path"),
                geology_path=payload.get("geology_path"),
            )
        except Exception as exc:
            return jsonify({"error": f"数据解析失败：{exc}"}), 400
        return jsonify(result), 200

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
