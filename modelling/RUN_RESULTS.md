# Execution results — 2026-11-13

All project writes, dependencies, caches and test artifacts are under `modelling/`.
Network approval was requested for dependency installation and the OpenF1 script.
Public documentation was consulted before approval; this sequencing mistake was
disclosed during execution. No other network data source was used.

## Lap-time regression continuation

Verified the existing lap-time implementation (`lap_model.py`, `lap_handoff.py`,
`lap_synthetic.py`, `lap_smoke.py` and `test_lap_model.py`) and completed its user
documentation in LAP_TIME_V2.md. README.md now reflects that the independent
Linear Regression task is implemented. Earlier unimplemented statements below
describe the state at the time of the podium migration.

Actual verification on 2026-11-13:
- `.venv\Scripts\python.exe -B -m pytest -q`: **100 passed in 144.44 seconds**.
- `.venv\Scripts\python.exe -B lap_smoke.py`: passed; produced an explicitly
  hypothetical synthetic scenario prediction of 85.5 seconds and saved evidence,
  model and smoke_result.json under
  `.test-work/lap_smoke_e07b7ce6290a44098e27c3999f1505c0/`.

The smoke target is exactly linear synthetic data; its near-zero errors do not
demonstrate real-world predictive accuracy. No network collection or real-data
training was performed during this continuation. No production artifact was
created. The implementation uses `predict_lap_time(lap_data)` with explicit mode
in DataFrame attrs; this differs from the proposed two-argument contract API and
is documented in LAP_TIME_V2.md. Contracts and M2 approval records were not edited.

## Random Forest-only podium migration

Implemented the podium portion of CONTRACT_v2.md. Both post_qualifying and
post_grid now use only RandomForestClassifier with the existing shallow-forest
defaults and median-imputation pipelines. Logistic Regression imports, scaling,
candidate comparison, winner selection and tie policy are removed from the
active training path. Linear Regression and Jolpica integration remain
unimplemented.

M1 still calls predict_podium(race_data, stage) and receives the same eight
columns, sorted scores and deterministic top-three selections. model_name is
always random_forest. V2 intentionally requires an approved M2 handoff in
DataFrame attrs for artifact-backed prediction, plus the existing explicit
post-grid verification flag. Source hashes, complete entrant/label matching,
reviewed crosswalks/lineage and pre-race cutoffs are checked before fitting or
serving a model. No real pilot handoff is created or automatically approved.

New artifacts are isolated under artifacts/v2/podium/. Metadata identifies
contract 2.0, task podium, model random_forest, stage/features, reviewed sources,
training cutoff/partitions, preprocessing, feature ranges, seed, library versions
and pipeline integrity hash. Old v1 artifacts (including Random Forests), missing
or malformed metadata, mismatched task/stage/model/schema, wrong libraries,
corrupted payloads and incompatible pipeline types are rejected explicitly.

Chronological complete-race 60/20/20 partitions, the ten-reviewed-race minimum,
fixed-model validation, train-plus-validation refit, final test evaluation,
stage-appropriate baselines and saved/API parity are preserved. All-null training
features now stop for an explicit modeling decision. Baselines without three
known positions are reported unavailable instead of inventing picks. Supporting
average-precision, Brier and fixed-0.5-threshold metrics are included alongside
the existing selection metrics.

Compatibility changes beyond unchanged M1 signature/output:
- Callers need stage-specific approved M2 handoff context; a grid boolean alone
  is insufficient.
- The training CLI requires --post-qualifying-handoff and --post-grid-handoff.
- evaluation.json has one validation/test result per stage; winner, candidate
  maps and tie_policy are removed.
- Legacy artifacts are preserved but cannot be relabeled/loaded as v2.

Changed implementation/configuration/documentation:
m3.py, podium_handoff.py (new), conftest.py (new), test_m3.py, test_rf.py (new),
pytest.ini, README.md, PODIUM_V2.md (new), and RUN_RESULTS.md.

Actual verification:
- Complete configured suite:
  .venv\Scripts\python.exe -B -m pytest -q
  **66 passed in 268.95 seconds (4 minutes 28 seconds), no warnings or failures.**
  This includes the existing collector/pilot tests, all seven unchanged M2
  verification tests, and new RF-only/artifact/handoff/leakage regressions.
- Initial run: 60 passed, six fixture setup errors and one null-comparison
  warning. Shared fixture discovery and None/NaN normalization were corrected
  before the successful full rerun.
- .venv\Scripts\python.exe -B m3.py --help completed successfully with the new
  required handoff options.
- Static inspection confirmed no sklearn.linear_model or scaling imports in
  the active podium module and unchanged predict_podium parameter names.
- SHA-256 checks confirmed all 109 protected files unchanged: both contracts,
  collection code, existing race datasets/caches, verification files and any
  pre-existing artifacts.

All model fitting was on clearly labeled SYNTHETIC-ONLY test handoffs and data.
Generated synthetic evidence/models stayed under modelling/.test-work/. No real
Grand Prix was used for training, no production artifact was created, no data was
fetched, and existing race data, collectors, contracts and M2 review files were
neither modified nor regenerated. The existing writing smoke script was not run.
See [PODIUM_V2.md](PODIUM_V2.md) for the implemented handoff/package conventions.


## Proposed v2 documentation update

Created [CONTRACT_v2.md](CONTRACT_v2.md) for the approved independent model tasks:
Random Forest Classifier for both podium stages, and Linear Regression for clean
practice flying laps with compound, tire age, track temperature, circuit and
driver context. It defines exact schemas, historical/scenario timing, proposed
age/weather assumptions, chronological evaluation, source conflict handling and
M1/M2/M3 handoffs.

OpenF1 and Jolpica are now approved in the proposed contract; Jolpica integration
remains unimplemented. Earlier reports below accurately describe the existing
OpenF1-only collection. No collection, model training, source-code migration,
Logistic Regression removal, dataset changes or verification-file changes were
performed in this documentation task. CONTRACT.md v1 remains unchanged.

The README distinguishes the proposed contract from current v1 functionality.
Tire-age numbering/reuse, the proposed 120-second weather freshness threshold,
clean-lap and wet/dry eligibility, cutoff evidence, final grids, cross-source
mappings and conflict decisions remain subject to M2 confirmation.


## Latest five-race pilot

Executed the fixed 2024 pilot through the existing collector. Only OpenF1 was
used. No historical model training, production artifacts, other seasons, or
additional Grands Prix were started. The contract and M1 prediction API are
unchanged. Network access for collection was approved.

| Grand Prix | Driver rows | Qualifying key | Race key | Practice source |
|---|---:|---:|---:|---|
| Bahrain | 20 | 9468 | 9472 | FP3, 9467 |
| Saudi Arabia | 20 | 9476 | 9480 | FP3, 9475 |
| Australia | 19 | 9484 | 9488 | FP3, 9483 |
| Japan | 20 | 9492 | 9496 | FP3, 9491 |
| China | 20 | 9664 | 9673 | FP1, 9663 |

**5/5 races collected successfully; 99 unique race/driver rows per stage.**
Australia's qualifying roster, qualifying classification, grid and race
classification all contain the same 19 drivers; no twentieth row was invented.
Normal GP race/qualifying sessions were selected, excluding China's sprint
events. The qualifying roster defines feature entrants; race outcomes and race
drivers are not used to construct or select prediction-feature rows.

Missing feature values across the 99 rows:

| Feature | Missing |
|---|---:|
| qualifying_position | 1 |
| qualifying_gap_seconds | 1 |
| practice_gap_seconds | 0 |
| qualifying_air_temp_c | 0 |
| qualifying_track_temp_c | 0 |
| qualifying_rainfall | 0 |
| grid_position (post-grid only) | 0 |

Both nulls belong to Zhou Guanyu (#24) in Saudi Arabia. OpenF1 qualifying
classification explicitly provides no position and Q1/Q2/Q3 durations all null.
The collector now suppresses his complete-looking in-lap as evidence of valid
qualifying pace. Missingness is preserved, not replaced with grid or a made-up
classification. This validity edge case has a regression test.

All 99 grids are populated, with unique positive grid positions within each race
and matching driver/session/meeting keys. Race classifications cover all feature
entrants without duplicates or extras. Separate labels contain 99 non-null binary
targets and exactly three positive labels per race (15 total). All feature keys
are unique. All five races passed both stage shape/value smoke validations;
post-grid uses an explicit local smoke-only verification attestation. The stored
reports retain `grid_verified: false` and `M2_approved: false`.

There were **no API failures or structurally incomplete races** in this pilot.
Every race nevertheless requires M2 verification. Reports include pit-out and
incomplete-lap exclusions and deleted/reinstated-lap messages (qualifying message
counts: Bahrain 2, Saudi Arabia 4, Australia 2, Japan 1, China 3). Pit-in/deleted
lap validity and official eligibility/grid/cutoff provenance remain review items.
The post-grid publication cutoff is unknown and explicitly reported; no inferred
cutoff or claim of verified historical availability is made.

Verification performed:

- `.venv\Scripts\python.exe collect_pilot.py`: 5/5 draft collections, 99 rows.
- `.venv\Scripts\python.exe collect_pilot.py --offline`: 5/5 from cache,
  with no missing cached responses or network requests.
- SHA-256 verification confirmed all **24 per-race/combined CSV files** were
  byte-for-byte identical after offline replay. Separate labels were checked:
  99 rows, zero missing labels, exactly 15 positive podium labels.
- `.venv\Scripts\python.exe -m pytest -q`: **31 passed in 16.55 seconds**.
  New regressions cover five-race aggregation, exact contract-only schemas,
  driver-number alignment, sprint exclusion, practice fallback, absent grids and
  classifications, ambiguous/duplicate labels, per-race failure isolation, and
  feature invariance when race outcomes change.
- Existing Bahrain `smoke.py`: both stages pass contract smoke checks and reject
  production predictions specifically because trained artifacts are absent.

Generated combined outputs in `data/pilot_2024/`: `post_qualifying_features.csv`,
`post_grid_features.csv`, `podium_labels.csv`, `race_manifest.csv`,
`quality_report.json`, `offline_quality_report.json`, and
`replay_verification.json`. Per-race directories retain raw JSON responses,
`draft_entrants.csv`, both stage-specific entrant CSVs, `podium_labels.csv`, and
live/offline quality reports. Stage CSVs contain only required contract columns;
metadata and targets are stored separately. No label-joined training file exists.

The pilot is ready for M2 review, not automatic training or expansion.

## Earlier Bahrain-only verification

- Installed pinned dependencies in `.venv/` using `uv`, with `.uv-cache/` local.
  Saved all installed versions in `requirements-lock.txt`.
- Executed `openf1_prototype.py` against Bahrain 2024. Retrieved 20 entrants,
  qualifying and FP3 laps, qualifying weather, both session classifications,
  sessions and qualifying race control. Saved raw successful responses.
- Executed `openf1_prototype.py --offline` successfully using cached data.
  All nine requested datasets, including the corrected grid, are now cached.
- Corrected starting-grid collection to use normal qualifying session `9468`
  within meeting `1229`, retaining same-meeting selection and excluding sprint
  qualifying. The race session remains `9472` for race drivers/results.
- Retrieved the corrected OpenF1 starting grid successfully (HTTP 200 during
  investigation; the regeneration fetched and cached 20 rows). Exact URL:
  `https://api.openf1.org/v1/starting_grid?session_key=9468`.
- Regenerated `draft_entrants.csv`, `post_qualifying_entrants.csv` (no grid
  feature), and `post_grid_entrants.csv` using only real OpenF1 responses. The
  other inputs were reused from the existing successful OpenF1 response cache.
- Verified **20/20 populated grid positions**, exactly integers 1–20, 20 unique
  driver assignments, and no duplicate drivers or grid positions. Every raw grid
  row matches meeting `1229` and qualifying session `9468`; the post-grid CSV
  driver-to-position mapping matches the raw response exactly. No required input
  values are missing in the combined draft.
- Executed `smoke.py`: **both post_qualifying and post_grid contract checks
  passed for all 20 drivers**. The post-grid check supplies an explicit local
  smoke-only `grid_verified=True` attestation after validating the source mapping.
  This exercises the existing contract without marking the draft M2-approved;
  `report.json` still records `grid_verified: false` pending M2 sign-off.
  Both production prediction calls then rejected specifically with
  `FileNotFoundError` for absent trained artifacts, as expected.
  See `data/2024_bahrain/smoke.json`.
- Executed the complete suite, `.venv\Scripts\python.exe -m pytest -q`:
  **23 passed in 23.63 seconds**, with no failed tests. Coverage includes invalid inputs, inference
  result leakage, deterministic ties, stage feature isolation, chronological
  partitions, candidate selection, all-null feature handling, artifact metadata,
  persistence/API parity, missing artifacts, and offline missing-session behavior.
  New regression coverage requires the normal same-meeting qualifying key for
  `starting_grid` even when race, sprint qualifying, and another meeting's normal
  qualifying sessions are present. It rejects fallback when normal qualifying is
  absent, duplicate drivers/positions, mismatched session/meeting keys, and grid
  assignments outside the entrant list.

The top-three grid baseline selections (unordered podium picks) are:

| Grid position | Driver number | Driver |
|---|---|---|
| 1 | 1 | Max Verstappen |
| 2 | 16 | Charles Leclerc |
| 3 | 63 | George Russell |

The training integration test uses ten synthetic races and writes test-only
artifacts under `.test-work/`. Those scores are software checks, not evidence of
real predictive accuracy. No production model artifact or historical performance
metric is claimed.

## Failures and handling

- Default MSYS Python has no pip. Standard-library venv creation failed in
  ensurepip; `uv pip install` successfully populated the local environment.
- Initial pytest temporary-folder/cache permissions conflicted with managed
  Windows ACLs. The tests now use ordinary workspace-local directories, disable
  pytest caching, and constrain test discovery. No escalation or ACL changes were
  used. Unreadable failed-run temporary folders were left in place and ignored.
- OpenF1 `/starting_grid?session_key=9472` returned **HTTP 404**. It was not
  replaced with qualifying classification or race-start position telemetry.
  Investigation confirmed that this was a wrong session identifier for this
  endpoint, not unavailable Bahrain historical grid data. This failure is now
  resolved by using qualifying session `9468`; all 20 grid positions are populated.

## Missing or unverified data

- Final grid data is now present and passes source-integrity/contract smoke
  checks. M2's production verification attestation is still required by the
  unchanged API. A CSV alone does not carry pandas DataFrame attributes.
- Lap validity: provisional pace excludes pit-out and incomplete laps but does
  not fully establish pit-in or deleted-lap exclusion. M2 must review validity
  against race-control/official sources before the draft becomes model input.
- Official qualifying classification, complete eligible entrant list, forecast
  cutoff provenance, and race-result status/target interpretation need M2 review.
  API fields exist, but retrieval alone is not verification.
- Reviewed multi-race history is absent. Chronological historical model choice
  and final-test evaluation therefore remain unexecuted on real data. One weekend
  supports only the data/inference smoke checks.

`data/2024_bahrain/report.json` records observed live endpoint outcomes;
`offline_report.json` records replay behavior. `README.md` describes commands,
M1 integration, verification attestation, and historical training requirements.
