import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from f1_dashboard import archive, demo

ROOT = Path(__file__).resolve().parents[1]


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        # Use future fixture starts so these flow checks remain useful after 2026.
        races = tuple(replace(r, local_date="2099-11-21", start_utc="2099-11-22T04:00:00Z") for r in demo.RACES)
        self.calendar_patch = patch.object(demo, "RACES", races)
        self.calendar_patch.start()
        self.addCleanup(self.calendar_patch.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()

    def assert_clean(self, app):
        self.assertEqual(len(app.exception), 0, str(app.exception))

    def test_readiness_generation_and_stale_output(self):
        app = self.app()
        self.assert_clean(app)
        self.assertTrue(app.button(key="generate").disabled)
        self.assertIn("Awaiting qualifying data.", [v.value for v in app.warning])
        app.selectbox(key="scenario").select("Qualifying ready").run()
        app.button(key="generate").click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.session_state["forecast"]["picks"]), 3)
        app.selectbox(key="race").select(demo.RACES[1].race_id).run()
        self.assertNotIn("forecast", app.session_state)
        app.selectbox(key="scenario").select("Qualifying weather missing").run()
        self.assertTrue(app.button(key="generate").disabled)
        self.assert_clean(app)

    def test_optional_practice_and_grid_update(self):
        app = self.app()
        app.selectbox(key="scenario").select("Qualifying ready").run()
        app.checkbox(key="practice").uncheck().run()
        app.button(key="generate").click().run()
        self.assert_clean(app)
        self.assertIsNone(app.session_state["forecast"]["input_snapshot"]["practice_available_utc"])
        original = app.session_state["forecast"]
        app.selectbox(key="scenario").select("Official grid ready").run()
        self.assertNotIn("forecast", app.session_state)
        app.button(key="generate").click().run()
        self.assertEqual(app.session_state["forecast"]["mode"], "grid-updated")
        self.assertNotEqual(app.session_state["forecast"]["forecast_id"], original["forecast_id"])
        self.assertEqual(original["mode"], "qualifying")
        self.assert_clean(app)

    def test_save_reload_and_pending_result(self):
        real_save, real_load = archive.save_snapshot, archive.load_snapshots
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch.object(archive, "save_snapshot", side_effect=lambda data: real_save(data, directory)), \
                 patch.object(archive, "load_snapshots", side_effect=lambda: real_load(directory)):
                app = self.app()
                app.selectbox(key="scenario").select("Qualifying ready").run()
                app.button(key="generate").click().run()
                app.button(key="save").click().run()
                self.assert_clean(app)
                app.button(key="save").click().run()
                self.assertEqual(len(list(directory.glob("*.json"))), 1)
                fresh = self.app()
                fresh.radio(key="page").set_value("Forecast archive").run()
                self.assert_clean(fresh)
                self.assertIn("Awaiting official race result. This demo does not fetch results.", [v.value for v in fresh.info])

    def test_seed_archive_comparison(self):
        with patch.object(archive, "load_snapshots", return_value=([], [])):
            app = self.app()
            app.radio(key="page").set_value("Forecast archive").run()
            self.assert_clean(app)
            self.assertEqual(app.metric[0].value, "2 / 3")
            self.assertIn("fictional", app.subheader[0].value)

    def test_lap_form(self):
        app = self.app()
        app.radio(key="page").set_value("Lap-time estimator").run()
        app.selectbox(key="lap_circuit").select("Lusail")
        app.selectbox(key="compound").select("HARD")
        app.number_input(key="age").set_value(20)
        app.number_input(key="temp").set_value(40.0)
        app.button[0].click().run()
        self.assert_clean(app)
        self.assertEqual(app.metric[0].value, "87.450 s")
        self.assertTrue(any("Typical test error: unavailable" in v.value for v in app.markdown))

    def test_empty_calendar_has_clear_message(self):
        with patch.object(demo, "upcoming_races", return_value=[]):
            app = self.app()
            self.assert_clean(app)
            self.assertTrue(any("No upcoming races" in v.value for v in app.warning))


if __name__ == "__main__":
    unittest.main()
