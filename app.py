"""Run with the project interpreter: python -m streamlit run app.py."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
import streamlit as st
from f1_dashboard import archive, demo, predictions, m3_bridge, ui
from f1_dashboard.contracts import matched_picks, readiness, utc

st.set_page_config(page_title="APEX | Race Intelligence", page_icon="🏎️", layout="wide")
ui.apply_theme()


with st.sidebar:
    ui.brand()
    page = st.radio("Workspace", ["Podium forecast", "Forecast archive", "Lap-time estimator", "Integration status"], key="page")
    ui.sidebar_note()

ui.topline(page)

if page == "Podium forecast":
    ui.hero("01 / RACE FORECAST", "Read the race.", "Call the podium.",
            "Qualifying pace. Session weather. Starting grid. Explore the three-driver podium set, in any finishing order.")
    st.caption("Real calendar entries · demo readiness, inputs and outputs. Scenarios do not report live race status.")
    races = demo.upcoming_races()
    if not races:
        st.warning("No upcoming races remain in the demo calendar. Ask M2 for an updated calendar snapshot.")
        st.caption(f"Static calendar checked {demo.CALENDAR_CHECKED}.")
        st.stop()
    with st.container(border=True, key="forecast_controls"):
        ui.section("Race weekend", "Set your demo scenario")
        race_column, scenario_column = st.columns([1.2, 1], gap="medium")
        with race_column:
            race_id = st.selectbox("Upcoming Grand Prix", [r.race_id for r in races],
                                   format_func=lambda value: next(f"{r.name} · {r.local_date}" for r in races if r.race_id == value),
                                   key="race")
        with scenario_column:
            scenario = st.selectbox("Demo readiness scenario", demo.SCENARIOS, key="scenario")
        practice = st.checkbox("Include available demo practice pace", value=True, key="practice")
    race = next(r for r in races if r.race_id == race_id)
    ui.race_banner(race)
    inputs = demo.load_demo_inputs(race, scenario, practice)
    state = readiness(inputs)
    ready = state.startswith("Ready")
    ui.section("Data readiness", "Demo input availability")
    ui.readiness_cards(inputs)
    (st.success if ready else st.warning)(state)
    include_grid = scenario == "Official grid ready"
    selection = (race_id, scenario, practice)
    if st.session_state.get("forecast_selection") != selection:
        st.session_state.pop("forecast", None)
        st.session_state["forecast_selection"] = selection
    if st.button("Generate demo forecast", disabled=not ready, type="primary", key="generate"):
        try:
            picks = predictions.predict_podium(inputs, include_grid)
            st.session_state["forecast"] = archive.make_snapshot(inputs, picks, include_grid)
        except ValueError as error:
            st.error(str(error))
    forecast = st.session_state.get("forecast")
    if forecast:
        ui.section("The podium set", "Three picks / any finishing order")
        ui.picks_cards(forecast["picks"], forecast["driver_names"])
        st.caption("Alphabetical display · no predicted P1/P2/P3 · no calibrated probabilities.")
        st.caption(f"{forecast['mode']} · {forecast['model_version']} · Cutoff {forecast['cutoff_utc']}")
        st.caption(f"Created {forecast['created_at_utc']}")
        if st.button("Save demo forecast to archive", key="save"):
            try:
                if datetime.now(timezone.utc) >= utc(forecast["race"]["start_utc"]):
                    raise ValueError("Race has started; this snapshot can no longer be saved as pre-race.")
                if st.session_state.get("saved_id") == forecast["forecast_id"]:
                    st.info("This forecast is already saved.")
                else:
                    archive.save_snapshot(forecast)
                    st.session_state["saved_id"] = forecast["forecast_id"]
                    st.success("Saved locally. Open Forecast archive to review or download it.")
            except (OSError, ValueError) as error:
                st.error(f"Could not save forecast: {error}")
    else:
        ui.empty_forecast(ready)
    with st.expander("Inspect demo inputs and forecast cutoff"):
        st.json(asdict(inputs))
        st.caption(f"Static calendar checked {demo.CALENDAR_CHECKED}. Source: {demo.CALENDAR_SOURCE}")
    st.caption("A grid update creates a new forecast. Saved qualifying forecasts stay unchanged.")

elif page == "Forecast archive":
    ui.hero("02 / FORECAST ARCHIVE", "Before the lights.", "After the flag.",
            "The original call, on the record. Revisit saved forecasts and compare the three-driver set with the actual podium.")
    st.info("DEMO archive · the Sample Grand Prix and its actual podium are fictional. New saves await a matching result.")
    try:
        records, errors = archive.load_snapshots()
    except OSError as error:
        records, errors = [], [f"Could not read local archive: {error}"]
    for error in errors:
        st.warning(error)
    records = sorted([demo.SAMPLE_FORECAST, *records], key=lambda item: item["created_at_utc"], reverse=True)
    ui.section("The forecast log", "Preserved snapshots")
    selected = st.selectbox("Saved forecast", range(len(records)),
                            format_func=lambda i: f"{records[i]['race']['name']} · {records[i]['mode']} · {records[i]['created_at_utc']} · {records[i]['forecast_id'][:8]}",
                            key="archive_record")
    record = records[selected]
    st.subheader(record["race"]["name"])
    ui.picks_cards(record["picks"], record["driver_names"])
    st.caption(f"Mode: {record['mode']} · Model: {record['model_version']}")
    st.caption(f"Created {record['created_at_utc']} · Input cutoff {record['cutoff_utc']}")
    result = demo.DEMO_RESULTS.get(record["race"]["race_id"])
    if result:
        st.metric("Podium picks matched (any order)", f"{matched_picks(record['picks'], result['podium'])} / 3")
        st.write("Actual podium — fictional demo result")
        st.write(" · ".join(f"P{position}: {code}" for position, code in enumerate(result["podium"], start=1)))
        st.caption(f"{result['source']} · Available {result['available_at_utc']}")
    else:
        st.info("Awaiting official race result. This demo does not fetch results.")
    st.download_button("Download saved forecast JSON", json.dumps(record, indent=2),
                       file_name=f"{record['forecast_id']}.json", mime="application/json")
    with st.expander("Saved input snapshot"):
        st.json(record["input_snapshot"])

elif page == "Integration status":
    ui.hero("04 / TEAM GARAGE", "Built to connect.", "Ready for handoff.",
            "A clear view of model deliveries and the data needed to move from the prototype to real predictions.")
    st.warning("Real model predictions are not enabled in this dashboard. The forecast and lap screens still use demo functions.")
    ui.section("Model delivery", "File presence / not approval")
    model_rows = m3_bridge.artifact_status()
    ui.pipeline_cards(model_rows)
    with st.expander("Model and metadata file details"):
        st.table(model_rows)
    st.caption("This checks file presence only. M3 validates hashes, schema, versions and handoff evidence during inference. Present files do not prove a model is usable.")
    st.subheader("What the team needs next")
    st.write("M2: reviewed race inputs, source availability at the forecast cutoff, driver/circuit identities and official grid evidence.")
    st.write("M3: trained model files with matching metadata, held-out evaluation and supported input categories/ranges.")
    st.info("Lap interface decision pending: M3's current model also needs a reviewed driver identity and race context. The four-input demo form stays available; real lap prediction needs an agreed driver policy or a model trained for those four inputs.")
    with st.expander("Developer setup and handoff details"):
        st.table(m3_bridge.dependency_status())
        st.code('& ".\\.venv\\Scripts\\python.exe" -m pip install -r requirements-models.txt', language="powershell")
        st.write("The callable bridge uses M3's integration_adapter with RaceInputs and explicit reviewed translation contexts. It preserves the adapter's evidence and result disclosures. It never trains a model or replaces a failed real prediction with demo output.")
        st.caption("See docs/M3_HANDOFF.md for current differences and the integration sequence.")

else:
    ui.hero("03 / LAP-TIME LAB", "Every millisecond.", "A little clearer.",
            "Choose a circuit and tire setup. Explore an illustrative clean-lap estimate, one scenario at a time.")
    st.info("DEMO formula · separate from the podium forecast · supported ranges are demo limits, not training coverage.")
    with st.form("lap_form"):
        ui.section("Build your lap", "Four inputs / one estimate")
        ui.compound_legend()
        left, right = st.columns(2)
        with left:
            circuit = st.selectbox("Circuit", list(predictions.CIRCUIT_BASE_SECONDS), key="lap_circuit")
            compound = st.selectbox("Tire compound", list(predictions.COMPOUND_PENALTY), key="compound")
        with right:
            age = st.number_input("Tire age (laps)", min_value=0, max_value=60, value=5, step=1, key="age")
            temp = st.number_input("Track temperature (°C)", min_value=10.0, max_value=65.0, value=35.0, step=0.5, key="temp")
        submitted = st.form_submit_button("Estimate demo lap time", type="primary")
    if submitted:
        try:
            estimate = predictions.estimate_lap(circuit, compound, age, temp)
            with st.container(border=True, key="lap_result"):
                ui.section("Your demo lap", "Clean lap / seconds")
                st.metric("Estimated clean lap time (demo)", f"{estimate.seconds:.3f} s")
                st.caption(f"Inputs: {circuit} · {compound} · {age} laps · {temp:g} °C")
                if estimate.test_mae_seconds is None:
                    st.write("Typical test error: unavailable — awaiting M3's held-out evaluation.")
                else:
                    st.write(f"Typical test error (MAE): {estimate.test_mae_seconds:.3f} s")
                st.caption(f"Model: {estimate.model_version}. Illustrative estimate; not a race or qualifying prediction.")
        except ValueError as error:
            st.error(str(error))

ui.footer()
