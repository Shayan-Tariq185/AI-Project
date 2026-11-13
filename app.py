"""Run with the project interpreter: python -m streamlit run app.py."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
import streamlit as st
from f1_dashboard import archive, demo, predictions
from f1_dashboard.contracts import matched_picks, readiness, utc

st.set_page_config(page_title="Apex | F1 Analytics", page_icon="🏎️", layout="wide")


def picks_cards(picks, names):
    for column, code in zip(st.columns(3), sorted(picks, key=lambda code: names[code])):
        with column.container(border=True):
            st.caption("PODIUM PICK · UNORDERED")
            st.subheader(names[code])
            st.caption(code)


with st.sidebar:
    st.title("APEX / F1")
    st.caption("AI2002 · Race prediction & analytics")
    page = st.radio("Workspace", ["Podium forecast", "Forecast archive", "Lap-time estimator"], key="page")
    st.divider()
    st.warning("DEMO MODE")
    st.caption("Synthetic session data and illustrative predictions. No live inputs or trained models connected.")
    st.caption("M1 · Shayan / Streamlit & integration")

st.caption("AI2002  /  FORMULA 1 ANALYTICS")

if page == "Podium forecast":
    st.title("The next podium.")
    st.write("Three drivers to watch. Any finishing order.")
    st.info("Real calendar entries · demo readiness, inputs and outputs. Scenarios do not report live race status.")
    races = demo.upcoming_races()
    if not races:
        st.warning("No upcoming races remain in the demo calendar. Ask M2 for an updated calendar snapshot.")
        st.caption(f"Static calendar checked {demo.CALENDAR_CHECKED}.")
        st.stop()
    race_id = st.selectbox("Upcoming Grand Prix", [r.race_id for r in races],
                           format_func=lambda value: next(f"{r.name} · {r.local_date}" for r in races if r.race_id == value),
                           key="race")
    race = next(r for r in races if r.race_id == race_id)
    st.caption(f"{race.circuit} · {race.local_date} (venue-local date) · Start {race.start_utc} (UTC)")
    scenario = st.selectbox("Demo readiness scenario", demo.SCENARIOS, key="scenario")
    practice = st.checkbox("Include available demo practice pace", value=True, key="practice")
    inputs = demo.load_demo_inputs(race, scenario, practice)
    state = readiness(inputs)
    ready = state.startswith("Ready")
    (st.success if ready else st.warning)(state)
    cols = st.columns(4)
    for col, label, available in zip(cols, ["Qualifying", "Practice (optional)", "Qualifying weather", "Official grid"],
                                    [inputs.qualifying_available_utc, inputs.practice_available_utc,
                                     inputs.weather_available_utc, inputs.grid_available_utc]):
        col.metric(label, "Available (demo)" if available else "Missing")
    include_grid = scenario == "Official grid ready"
    st.caption("Grid-ready generates an updated forecast; previously saved qualifying forecasts stay unchanged.")
    with st.expander("Inspect demo inputs and forecast cutoff"):
        st.json(asdict(inputs))
        st.caption(f"Static calendar checked {demo.CALENDAR_CHECKED}. Source: {demo.CALENDAR_SOURCE}")
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
        st.subheader("Demo podium picks")
        picks_cards(forecast["picks"], forecast["driver_names"])
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

elif page == "Forecast archive":
    st.title("Before the lights went out.")
    st.write("Preserved forecast snapshots, compared by driver overlap.")
    st.info("DEMO archive · the Sample Grand Prix and its actual podium are fictional. New saves await a matching result.")
    try:
        records, errors = archive.load_snapshots()
    except OSError as error:
        records, errors = [], [f"Could not read local archive: {error}"]
    for error in errors:
        st.warning(error)
    records = sorted([demo.SAMPLE_FORECAST, *records], key=lambda item: item["created_at_utc"], reverse=True)
    selected = st.selectbox("Saved forecast", range(len(records)),
                            format_func=lambda i: f"{records[i]['race']['name']} · {records[i]['mode']} · {records[i]['created_at_utc']} · {records[i]['forecast_id'][:8]}",
                            key="archive_record")
    record = records[selected]
    st.subheader(record["race"]["name"])
    picks_cards(record["picks"], record["driver_names"])
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

else:
    st.title("Find your lap time.")
    st.write("Estimate a clean lap from four inputs.")
    st.info("DEMO formula · separate from the podium forecast · supported ranges are demo limits, not training coverage.")
    with st.form("lap_form"):
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
            st.metric("Estimated clean lap time (demo)", f"{estimate.seconds:.3f} s")
            st.caption(f"Inputs: {circuit} · {compound} · {age} laps · {temp:g} °C")
            if estimate.test_mae_seconds is None:
                st.write("Typical test error: unavailable — awaiting M3's held-out evaluation.")
            else:
                st.write(f"Typical test error (MAE): {estimate.test_mae_seconds:.3f} s")
            st.caption(f"Model: {estimate.model_version}. Illustrative estimate; not a race or qualifying prediction.")
        except ValueError as error:
            st.error(str(error))

st.divider()
st.caption("APEX / AI2002 · Student prototype · Demo inputs and outputs")
