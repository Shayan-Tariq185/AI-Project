# F1 Race Prediction and Analytics Dashboard

AI2002 semester project, built with Streamlit by a three-person team.

## Features

- **Podium forecast:** choose a real upcoming Grand Prix, inspect readiness, then see three unordered podium picks after qualifying. Use qualifying pace, available practice pace and qualifying-session weather. The FIA final starting grid enables an updated forecast. Preserve timestamped pre-race snapshots and compare against the actual podium by set overlap (0–3 matches).
- **Lap-time estimator:** a separate model estimates clean lap time in seconds from circuit, tire compound, tire age in laps and track temperature in °C. Show held-out test error in seconds once available.

## Prototype status

**All session inputs, picks, lap estimates and archive results are demo-only. No live API or trained model is connected.** The selector uses a small static calendar snapshot checked on **13 November 2026**: Las Vegas, Qatar and Abu Dhabi. Dates/start times come from the [official calendar](https://www.formula1.com/en/racing/2026) and [official local start times](https://www.formula1.com/en/latest/article/official-grand-prix-start-times-for-2026-f1-season-confirmed.2UgPfArqH76tzlOYh21jSG). Race dates are venue-local; timestamps are UTC. Refresh this fixture before a later demo. It is not a full/live calendar.

The forecast page starts at **Awaiting qualifying data.** Change **Demo readiness scenario** to demonstrate qualifying-ready, official-grid-ready or missing-weather states. These scenarios do not report actual readiness. Practice is optional. An illustrative heuristic selects three drivers; no calibrated probabilities or predicted finishing positions are produced. Equal-sized cards display names alphabetically, never P1/P2/P3.

The archive includes a **fictional Sample Grand Prix**, fictional result and a **2 / 3** match example. New saves remain pending until a matching result is supplied. Snapshots persist across local app restarts under ignored `data/saved_forecasts/`; download JSON for a portable copy. Hosted local storage may be ephemeral and must be replaced with durable shared storage for deployment. No official result ingestion or scheduler exists yet. The lap formula has no measured test error; the UI says so.

## Windows setup and launch

Run in the repository folder. Python 3.11+ is required. Shayan's installed Python was found here, even though `python` and `py` do not resolve:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
```

On another machine use `py -m venv .venv` or your interpreter's absolute path for the first command. Activation is unnecessary; no execution-policy change is needed. Open **http://localhost:8501** if the browser does not open. Stop with **Ctrl+C**.

After setup, launch with:

```powershell
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
```

Behavior checks:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

## Team ownership

| Member | Ownership |
| --- | --- |
| M1 — Shayan | Streamlit interface, data/model integration, deployment, live demo |
| M2 | OpenF1 practice, qualifying, weather, race results, laps and tire stints; Jolpica historical starting grids; FIA published final grid for upcoming races; driver/lap datasets |
| M3 | Separate podium and lap-time models, training/evaluation, saved artifacts, prediction functions, input/output contracts and metrics |

**[docs/INTEGRATION.md](docs/INTEGRATION.md)** specifies the proposed handoff, units, missingness, evaluation and forecast cutoff rules. Agree on exact feature definitions before replacing demo adapters.

| File | Purpose |
| --- | --- |
| `app.py` | Forecast, archive and lap estimator screens |
| `f1_dashboard/demo.py` | Replaceable calendar, synthetic inputs and archive/result fixtures |
| `f1_dashboard/predictions.py` | Replaceable demo prediction functions |
| `f1_dashboard/contracts.py` | Typed inputs, readiness, input/cutoff validation and comparison |
| `f1_dashboard/archive.py` | Immutable local JSON snapshots |
| `tests/` | Forecast integrity, storage and Streamlit flow checks |

## Branch workflow

**member branches → dev → main**

- `m1-streamlit`: Shayan's UI/integration work; open PRs against `dev`.
- `dev`: team integration and combined testing.
- `main`: final tested project; the team merges `dev` after validation.

Each member uses their own branch. Shayan runs all Git/GitHub commands. Review specific files before staging; exclude environments, runtime snapshots, secrets and unrelated files. The unrelated local `ghghg` file is untouched.

## Deployment handoff

After team testing, use a Streamlit-compatible Python host with entry point `app.py` and dependencies from `requirements.txt`. The demo needs no credentials. Future live credentials belong in environment variables or Streamlit secrets. Confirm durable writable archive storage before shared use. This deliverable runs locally; nothing has been deployed.
