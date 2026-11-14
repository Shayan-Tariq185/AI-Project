# OpenF1 M3 prototype

Podium implementation follows `CONTRACT_v2.md` (Random Forest only). All source, environments, caches, data and
test artifacts live in this directory. Python used for verification: CPython
3.14.5 on Windows. `requirements-lock.txt` records every installed dependency;
`requirements.txt` pins direct dependencies.

## Contract v2 podium migration

[CONTRACT_v2.md](CONTRACT_v2.md) defines the approved independent model tasks.
The podium implementation now uses Random Forest Classifier only for both
post-qualifying and post-grid stages. Its prediction signature and eight output
columns are unchanged. [PODIUM_V2.md](PODIUM_V2.md) documents artifact migration,
M2 handoff requirements and the updated training workflow.

The Linear Regression lap-time task is implemented separately in `lap_model.py`.
See [LAP_TIME_V2.md](LAP_TIME_V2.md) for its API, evidence requirements and limits.
The [M3-to-M1 integration adapter](INTEGRATION_ADAPTER.md) translates dashboard
requests using explicit reviewed context and preserves M3 evidence and artifact
validation. M1 wiring remains a separate integration step.
OpenF1 and Jolpica are approved sources in the contract, but no Jolpica integration
or new data collection is included. Original CONTRACT.md, collected race datasets
and M2 verification files remain unchanged.

Contract v2 is not an M2 approval. Production training/scoring requires an
explicit approved handoff with matching features, labels where needed,
crosswalks, lineage, source hashes and verified prediction cutoffs. The
unreviewed five-race pilot is not authorized for production training.

## Run from this directory (PowerShell)

```powershell
# Setup on another machine; these commands require approved network access.
py -m venv .venv
uv pip install --python .venv\Scripts\python.exe --cache-dir .uv-cache -r requirements-lock.txt

# Read-only network collection (request approval before running).
.venv\Scripts\python.exe openf1_prototype.py --year 2024 --country Bahrain

# Replay without network. Missing cache entries are recorded, not fetched.
.venv\Scripts\python.exe openf1_prototype.py --year 2024 --country Bahrain --offline
.venv\Scripts\python.exe smoke.py
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

The collector caches successful JSON arrays, spaces requests, retries transient
errors, and writes `data/2024_bahrain/draft_entrants.csv` and `report.json`.
Raw race results are retained separately and never joined to inference features.
The collector also writes `post_qualifying_entrants.csv` (without grid) and
`post_grid_entrants.csv` (with grid). Starting-grid requests use the normal
qualifying session within the race meeting, excluding sprint qualifying.
The draft does **not** establish official lap validity, a verified final grid,
complete eligibility, or historical availability at the stated cutoff. It must
not be treated as an M2-approved training table. Pit-out and incomplete laps are
excluded; pit-in/deleted laps still require review. Track evolution also affects
best-lap comparisons. Weather medians and rainfall come from one weather endpoint.

## M1 API

```python
from m3 import predict_podium
race_data.attrs['m2_handoff_path'] = 'path/to/approved/stage/handoff.json'
predictions = predict_podium(race_data, 'post_qualifying')
# Use the post_grid stage's approved handoff and explicit grid attestation:
race_data.attrs['m2_handoff_path'] = 'path/to/approved/grid/handoff.json'
race_data.attrs['grid_verified'] = True
predictions = predict_podium(race_data, 'post_grid')
```

Missing trained artifacts raise `FileNotFoundError`. There is no mock fallback.
Post-race fields are rejected by the public inference API. Qualifying-stage
features exclude grid even if that column is provided. Outputs rank every driver
with deterministic number-based tiebreaks and exactly three unordered selections;
probabilities are independent and not guaranteed calibrated.

## Five-race 2024 pilot (no model training)

```powershell
# Approved network access required for uncached OpenF1 responses.
.venv\Scripts\python.exe collect_pilot.py
# Replay the same fixed scope with no network access.
.venv\Scripts\python.exe collect_pilot.py --offline
```

`collect_pilot.py` reuses the existing `build()` collector for Bahrain, Saudi
Arabia, Australia, Japan and China only. There is no season-expansion option.
Normal race and qualifying sessions are matched within one meeting; sprint race,
sprint qualifying and shootout sessions are excluded by exact session-name
selection. Features use the qualifying-session roster, not race drivers or race
classification coverage. Joins use race ID and driver number, never display names
or row order. The practice roster is cross-checked for identity discrepancies.
China uses Practice 1 because this sprint weekend has no FP3.

Stage CSVs now contain **exactly the required contract columns**: identity plus
the six shared features, and grid position only for post-grid. Optional source
metadata remains in `draft_entrants.csv` and reports. No outcomes, race telemetry,
labels, dates or source metadata are added to the stage feature tables.
`podium_labels.csv` stores just race ID, driver number and nullable
`is_podium_actual`. Ambiguous/missing/duplicate classifications produce null
labels with review reasons. DNF/DNS/DSQ map to zero according to the contract.

Combined historical tables live in `data/pilot_2024/`:

- `post_qualifying_features.csv` and `post_grid_features.csv`: separate stage
  datasets with 99 driver rows each (Australia has 19 entrants).
- `podium_labels.csv`: 99 separately keyed labels; never joined into predictions.
- `race_manifest.csv`: race dates, meeting/session keys and review flags.
- `quality_report.json` and `offline_quality_report.json`: all per-race reports,
  missing-value totals, source coverage, identity checks and request outcomes.
- `replay_verification.json`: CSV hashes from the verified offline replay.

Each `data/2024_<country>/` directory contains raw response caches, draft and stage
CSVs, separate labels, and live/offline quality reports. A run continues to the
remaining races if one fails; the failed/incomplete race is explicitly reported.
Each report distinguishes collection completeness from M2 approval. No race is
automatically approved. Both stage validations are exercised per race, with an
explicit smoke-only grid attestation for post-grid; production M2 attestation
requirements are unchanged.

The HTTP client uses a shared minimum 2.1-second request interval across race
clients, caches successful responses, and retries transient failures. This keeps
the sequential run below OpenF1's documented 3 requests/second and 30/minute
limits. Offline replay records cache misses and never requests the network.

Lap quality reports include pit-out/incomplete/missing-lap exclusions, raw driver
coverage, and qualifying/practice lap deletion/reinstatement messages. Pace is
still provisional pending M2 review of deleted/reinstated and pit-in laps. If
qualifying classification explicitly records no valid segment time, the driver's
qualifying gap remains null despite a complete-looking in-lap. In this pilot,
Zhou Guanyu (#24), Saudi Arabia, has null qualifying position and gap; these are
the only missing feature values. No replacement values are invented.

Forecast publication times, official lap validity, final grid verification and
eligibility remain M2 review items for all five races. Session-end timestamps are
intended post-qualifying cutoffs, not proof of historic publication availability;
the post-grid publication cutoff is explicitly unknown. Draft collection success
does not imply fitness for training. The pilot must be reviewed before expanding.

## Training on reviewed M2 history

Only use complete, reviewed Grand Prix entrant tables. M2 supplies `race_date`
(UTC-compatible date), binary `is_podium_actual`, and verified final grid positions
alongside contract fields. M2 must resolve ambiguous classifications and statuses
before handoff; do not derive targets from live position streams. At least ten
reviewed races are required by this prototype's guardrail, not as a claim of
statistical sufficiency.

```powershell
.venv\Scripts\python.exe m3.py reviewed_history.csv --grid-verified --post-qualifying-handoff path/to/qualifying/handoff.json --post-grid-handoff path/to/grid/handoff.json
```

The first 60% of complete races train the fixed shallow Random Forest, the next
20% provide chronological validation, and the final 20% provide final evaluation.
Both stages share complete-race partitions. Each stage has training-only median
imputation, with no scaling or Logistic Regression candidate. Entirely missing
training features require an explicit modeling decision. The fixed forest is
refit on train plus validation before one final test evaluation.

artifacts/v2/podium/evaluation.json records partition counts/date ranges, one
validation/test result per stage, baseline coverage, selection metrics, average
precision, Brier score and fixed-threshold precision/recall. The old winner/tie
report fields are removed. Persisted pipelines and metadata identify contract
2.0 and random_forest, and API parity is checked after saving. Legacy artifacts
are explicitly incompatible; only trusted local joblib artifacts may be loaded.

Tests use synthetic fixtures to exercise training and persistence; their metrics
are not historical performance evidence. Test artifacts remain in `.test-work/`.
No production artifacts are generated from the collected pilot races.

## Collected Bahrain 2024 data

The live run retrieved eight sessions, 20 drivers, 267 qualifying laps, 311 FP3
laps, 77 qualifying weather observations, 20 qualifying classifications, 20 race
classifications and 20 qualifying race-control messages. Qualifying and practice
gaps, qualifying classification and weather are populated for all 20 entrants.
The initial `starting_grid?session_key=9472` request used the race session and
returned HTTP 404. The corrected request uses normal qualifying session `9468`
and returns all 20 grid assignments, with unique positions 1–20. The collector
rejects mismatched meeting/session keys, duplicate grid drivers or positions, and
drivers outside the entrant list. It does not infer grid from qualifying results.

`smoke.py` checks both stage CSVs. It verifies the post-grid mapping against the
raw OpenF1 starting-grid response before applying an explicit local smoke-test
verification attestation. Both stages must pass contract validation and then
reject prediction specifically because trained artifacts are absent. This local
check does not set the collector's `grid_verified` flag or replace M2 sign-off.

See `data/2024_bahrain/report.json` for per-request results and review blockers.
