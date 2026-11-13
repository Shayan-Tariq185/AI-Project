import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from f1_dashboard import archive, demo, predictions
from f1_dashboard.contracts import matched_picks, readiness

NOW = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)


class ForecastTests(unittest.TestCase):
    def inputs(self, scenario="Qualifying ready", practice=True):
        return demo.load_demo_inputs(demo.RACES[0], scenario, practice, NOW)

    def test_readiness_states(self):
        for scenario, expected in zip(demo.SCENARIOS, ["Awaiting qualifying data.",
                "Ready for qualifying forecast", "Ready for grid-updated forecast",
                "Awaiting qualifying-session weather."]):
            with self.subTest(scenario=scenario):
                self.assertEqual(readiness(self.inputs(scenario)), expected)

    def test_unready_inference_rejected(self):
        for scenario in ("Before qualifying", "Qualifying weather missing"):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                predictions.predict_podium(self.inputs(scenario))

    def test_unique_unordered_picks_with_optional_practice(self):
        for practice in (True, False):
            inputs = self.inputs(practice=practice)
            picks = predictions.predict_podium(inputs)
            names = {d.driver_id: d.name for d in inputs.drivers}
            self.assertEqual(len(set(picks)), 3)
            self.assertEqual(picks, sorted(picks, key=lambda code: names[code]))

    def test_grid_update_changes_demo_picks(self):
        inputs = self.inputs("Official grid ready")
        self.assertNotEqual(set(predictions.predict_podium(inputs)),
                            set(predictions.predict_podium(inputs, True)))

    def test_grid_update_requires_grid(self):
        with self.assertRaises(ValueError):
            predictions.predict_podium(self.inputs(), True)

    def test_late_input_rejected(self):
        for field in ("qualifying_available_utc", "practice_available_utc",
                      "weather_available_utc", "grid_available_utc"):
            inputs = replace(self.inputs("Official grid ready"),
                             **{field: (NOW + timedelta(seconds=1)).isoformat()})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "after.*cutoff"):
                predictions.predict_podium(inputs, True)

    def test_race_start_closes_inference(self):
        inputs = replace(self.inputs(), cutoff_utc=demo.RACES[0].start_utc)
        self.assertEqual(readiness(inputs), "Forecast window closed")
        with self.assertRaises(ValueError):
            predictions.predict_podium(inputs)

    def test_invalid_driver_features_rejected(self):
        inputs = self.inputs("Official grid ready")
        for driver in (replace(inputs.drivers[0], qualifying_delta_s=float("nan")),
                       replace(inputs.drivers[0], practice_delta_s=-1),
                       replace(inputs.drivers[0], grid_position=1)):
            invalid = replace(inputs, drivers=(driver, *inputs.drivers[1:]))
            with self.subTest(driver=driver), self.assertRaises(ValueError):
                predictions.predict_podium(invalid, True)

    def test_podium_comparison_ignores_order(self):
        self.assertEqual(matched_picks(["NOR", "LEC", "VER"], ["VER", "NOR", "PIA"]), 2)
        self.assertEqual(matched_picks(["NOR", "LEC", "VER"], ["VER", "NOR", "LEC"]), 3)
        with self.assertRaises(ValueError):
            matched_picks(["NOR", "NOR", "VER"], ["VER", "NOR", "PIA"])

    def test_calendar_filters_started_races(self):
        self.assertEqual(len(demo.upcoming_races(NOW)), 3)
        self.assertEqual(demo.upcoming_races(datetime(2027, 1, 1, tzinfo=timezone.utc)), [])

    def test_snapshots_preserve_qualifying_when_grid_changes(self):
        inputs = self.inputs()
        original = archive.make_snapshot(inputs, predictions.predict_podium(inputs), False, NOW)
        updated_inputs = self.inputs("Official grid ready")
        updated = archive.make_snapshot(updated_inputs, predictions.predict_podium(updated_inputs, True), True, NOW)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = archive.save_snapshot(original, directory)
            before = path.read_bytes()
            archive.save_snapshot(updated, directory)
            records, errors = archive.load_snapshots(directory)
            self.assertFalse(errors)
            self.assertEqual(len(records), 2)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual({r["mode"] for r in records}, {"qualifying", "grid-updated"})
            self.assertEqual(original["input_snapshot"]["cutoff_utc"], inputs.cutoff_utc)

    def test_save_time_and_driver_field_enforced(self):
        inputs = self.inputs()
        picks = predictions.predict_podium(inputs)
        for instant in (NOW - timedelta(seconds=1), datetime(2027, 1, 1, tzinfo=timezone.utc)):
            with self.assertRaises(ValueError):
                archive.make_snapshot(inputs, picks, False, instant)
        with self.assertRaises(ValueError):
            archive.make_snapshot(inputs, ["NOR", "VER", "UNKNOWN"], False, NOW)

    def test_corrupt_archive_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "bad.json").write_text("{broken", encoding="utf-8")
            records, errors = archive.load_snapshots(directory)
            self.assertEqual(records, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("bad.json", errors[0])


class LapTests(unittest.TestCase):
    def test_lap_seconds_and_no_invented_error(self):
        result = predictions.estimate_lap("Las Vegas", "SOFT", 5, 35)
        self.assertAlmostEqual(result.seconds, 95.225)
        self.assertIsNone(result.test_mae_seconds)

    def test_lap_supported_boundary_values(self):
        for circuit in predictions.CIRCUIT_BASE_SECONDS:
            for compound in predictions.COMPOUND_PENALTY:
                for age, temp in ((0, 10), (60, 65)):
                    self.assertGreater(predictions.estimate_lap(circuit, compound, age, temp).seconds, 0)

    def test_lap_rejects_invalid_inputs(self):
        for args in (("Unknown", "SOFT", 5, 35), ("Las Vegas", "WET", 5, 35),
                     ("Las Vegas", "SOFT", -1, 35), ("Las Vegas", "SOFT", 61, 35),
                     ("Las Vegas", "SOFT", 1.5, 35), ("Las Vegas", "SOFT", 5, float("nan")),
                     ("Las Vegas", "SOFT", 5, 66)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                predictions.estimate_lap(*args)


if __name__ == "__main__":
    unittest.main()
