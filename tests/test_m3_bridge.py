from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from f1_dashboard import demo, m3_bridge, model_worker
from f1_dashboard.predictions import LapEstimate


@dataclass
class PodiumOutput:
    picks: list
    model_version: str
    evidence: dict


@dataclass
class LapOutput:
    estimate: LapEstimate
    is_hypothetical: bool
    support_status: str
    evidence: dict
    artifact_metadata: dict


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.inputs = demo.load_demo_inputs(demo.RACES[0], "Qualifying ready", True,
                                            datetime(2026, 11, 13, 15, tzinfo=timezone.utc))
        self.context = {"handoff_path": "missing-test-evidence.json", "drivers": [
            {"dashboard_driver_id": driver.driver_id, "driver_id": f"synthetic-{driver.driver_id}",
             "driver_number": number, "qualifying_position": number}
            for number, driver in enumerate(self.inputs.drivers, start=1)],
            "qualifying_air_temp_c": 24.0,
            "qualifying_gap_definition": "best_valid_all_segments_minus_session_best_seconds",
            "practice_gap_definition": "best_valid_selected_common_practice_minus_session_best_seconds",
            "reviewer": "SYNTHETIC bridge test", "reviewed_at_utc": "2026-11-13T16:00:00Z",
            "grid_verified": False}

    def call(self):
        return m3_bridge.predict_podium(self.inputs, context=self.context)

    def test_missing_dependency_is_explicit_and_never_falls_back(self):
        missing = [{"Package": "scikit-learn", "Status": "Setup needed"}]
        with patch.object(m3_bridge, "dependency_status", return_value=missing), \
             patch.object(m3_bridge.subprocess, "run") as runner:
            with self.assertRaisesRegex(m3_bridge.ModelUnavailable, "scikit-learn"):
                self.call()
            runner.assert_not_called()

    def test_grid_attestation_not_invented(self):
        with self.assertRaisesRegex(ValueError, "explicit grid"):
            m3_bridge.predict_podium(self.inputs, True, context=self.context)

    def test_lap_requires_explicit_context_and_provenance(self):
        for context in ({}, {"evidence_path": "missing.json", "mode": "scenario"}):
            with self.subTest(context=context), self.assertRaises(ValueError):
                m3_bridge.estimate_lap("Las Vegas", "SOFT", 5, 35, context=context)

    def test_worker_failure_is_not_converted_to_prediction(self):
        result = SimpleNamespace(returncode=1, stdout=json.dumps({"ok": False, "error": "No trained artifact"}))
        with patch.object(m3_bridge, "dependency_status", return_value=[]), \
             patch.object(m3_bridge.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(m3_bridge.ModelUnavailable, "No trained artifact"):
                self.call()

    def test_bad_process_response_and_timeout_reported(self):
        with patch.object(m3_bridge, "dependency_status", return_value=[]):
            for stdout in ("not JSON", "[]", '{"ok": true}'):
                with patch.object(m3_bridge.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=stdout)):
                    with self.assertRaises(m3_bridge.ModelUnavailable):
                        self.call()
            with patch.object(m3_bridge.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 60)):
                with self.assertRaisesRegex(m3_bridge.ModelUnavailable, "could not complete"):
                    self.call()

    def test_files_present_are_not_reported_as_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertTrue(all(row["Status"].startswith("Missing:") for row in m3_bridge.artifact_status(root)))
            directory = root / "modelling/artifacts/v2/podium"
            directory.mkdir(parents=True)
            (directory / "post_grid.joblib").write_bytes(b"not a real model")
            (directory / "post_grid.json").write_text("{}")
            row = next(row for row in m3_bridge.artifact_status(root) if row["Task"] == "Grid-updated podium")
            self.assertEqual(row["Status"], "Files present; validation pending")

    def test_transport_preserves_inputs_and_context_without_mutating_caller(self):
        output = {"picks": ["VER", "NOR", "PIA"], "model_version": "test", "evidence": {"handoff_id": "TEST"}}
        reply = SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "prediction": output}))
        with patch.object(m3_bridge, "dependency_status", return_value=[]), \
             patch.object(m3_bridge.subprocess, "run", return_value=reply) as runner:
            self.assertEqual(self.call(), output)
            payload = json.loads(runner.call_args.kwargs["input"])
            self.assertEqual(payload["inputs"], json.loads(json.dumps(asdict(self.inputs))))
            self.assertEqual(payload["context"]["drivers"], self.context["drivers"])
            self.assertEqual(payload["context"]["handoff_path"], str(Path(self.context["handoff_path"]).resolve()))
            self.assertEqual(self.context["handoff_path"], "missing-test-evidence.json")

    def test_worker_delegates_to_adapter_and_preserves_podium_wrapper(self):
        output = PodiumOutput(["LEC", "NOR", "VER"], "test-version", {"handoff_id": "TEST", "source_hashes": {"a": "hash"}})
        def predict(inputs, include_grid, *, context):
            self.assertEqual(inputs, self.inputs)
            self.assertFalse(include_grid)
            self.assertEqual(context.drivers.to_dict("records"), self.context["drivers"])
            self.assertEqual(context.reviewer, self.context["reviewer"])
            return output
        adapter = SimpleNamespace(PodiumContext=lambda **kwargs: SimpleNamespace(**kwargs), predict_podium=predict)
        with patch.dict(sys.modules, {"integration_adapter": adapter}):
            result = model_worker.run({"task": "podium", "inputs": asdict(self.inputs),
                                       "include_grid": False, "context": self.context})
        self.assertEqual(result, asdict(output))

    def test_lap_wrapper_keeps_disclosures_and_does_not_choose_a_test_metric(self):
        output = LapOutput(LapEstimate(90.5, None, "test-version"), True, "numeric_extrapolation",
                           {"handoff_id": "TEST"}, {"evaluation": {"test": {"metrics": {"mae": 0.85}}}})
        def estimate(circuit, compound, age, temp, *, context):
            self.assertEqual((circuit, compound, age, temp), ("Las Vegas", "SOFT", 5, 35))
            self.assertEqual(context.row["driver_id"], "explicit-driver")
            return output
        adapter = SimpleNamespace(LapContext=lambda **kwargs: SimpleNamespace(**kwargs), estimate_lap=estimate)
        with patch.dict(sys.modules, {"integration_adapter": adapter}):
            result = model_worker.run({"task": "lap_time", "circuit": "Las Vegas", "compound": "SOFT",
                                       "tire_age_laps": 5, "track_temp_c": 35,
                                       "context": {"row": {"driver_id": "explicit-driver"}}})
        self.assertEqual(result, asdict(output))
        self.assertIsNone(result["estimate"]["test_mae_seconds"])

    def test_optional_real_worker_rejects_missing_reviewed_evidence(self):
        if any(row["Status"] != "Matches" for row in m3_bridge.dependency_status()):
            self.skipTest("Optional M3 environment not installed.")
        with self.assertRaisesRegex(m3_bridge.ModelUnavailable, "Cannot read"):
            self.call()


if __name__ == "__main__":
    unittest.main()
