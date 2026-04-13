from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402


class LabApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = create_app().test_client()
        self.sample_dir = BACKEND_DIR / "sample_data"

    def test_default_lab_run_returns_unified_state(self) -> None:
        response = self.client.get("/api/lab/run")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["lab_name"], "rockburst-agent-lab")
        self.assertIn("state_snapshot", payload)
        self.assertEqual(
            set(payload["state_snapshot"].keys()),
            {"timestamp", "chainage", "microseismic_features", "tbm_features", "geology_features", "risk_context"},
        )
        self.assertEqual(len(payload["agents"]["experiment_agent"]["experiment_scenarios"]), 5)
        self.assertEqual(payload["agents"]["microseismic_agent"]["agent_implementation"], "openclaw")
        self.assertIn("recommended_plan", payload["closed_loop_output"])

    def test_multipart_upload_runs_with_three_data_sources(self) -> None:
        with (
            (self.sample_dir / "microseismic.csv").open("rb") as microseismic_file,
            (self.sample_dir / "tbm.csv").open("rb") as tbm_file,
            (self.sample_dir / "geology.json").open("rb") as geology_file,
        ):
            response = self.client.post(
                "/api/lab/run",
                data={
                    "microseismic_file": (microseismic_file, "microseismic.csv"),
                    "tbm_file": (tbm_file, "tbm.csv"),
                    "geology_file": (geology_file, "geology.json"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["upload"]["mode"], "multipart")
        self.assertEqual(
            payload["upload"]["received"],
            ["geology_file", "microseismic_file", "tbm_file"],
        )
        self.assertGreater(payload["state_snapshot"]["microseismic_features"]["event_count"], 0)


if __name__ == "__main__":
    unittest.main()
