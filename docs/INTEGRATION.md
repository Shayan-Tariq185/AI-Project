# M2 / M3 integration handoff

This proposed contract is implemented by the prototype. Agree on feature definitions, transformations, missingness and units before substituting real adapters/models.

## M2: upcoming-race adapter

Replace `demo.upcoming_races()` and `demo.load_demo_inputs()` with functions returning `Race` / `RaceInputs` from `f1_dashboard/contracts.py`. Keep an explicit demo/live distinction and offline fixtures.

| Field | Meaning |
| --- | --- |
| `race_id` | Stable season/event identity shared by features, snapshots and results |
| `name`, `circuit`, `local_date`, `start_utc` | Calendar metadata, venue-local date, official UTC start instant |
| `cutoff_utc` | Information cutoff; timezone-aware UTC ISO 8601 |
| `qualifying_available_utc` | When included qualifying input became available |
| `practice_available_utc` | Latest included practice availability time, null if absent |
| `weather_available_utc` | When qualifying-session weather became available |
| `grid_available_utc` | When FIA's published final starting grid became available, null until published |
| `qualifying_track_temp_c`, `qualifying_rainfall` | Qualifying-session weather; °C and boolean |
| `drivers` | Complete driver field, stable IDs and display names |
| per-driver `qualifying_delta_s` | Representative clean qualifying pace delta to session best, seconds |
| per-driver `practice_delta_s` | Representative available clean practice pace delta, seconds, or null |
| per-driver `grid_position` | Official final starting position as integer, null until published |

Agree on qualifying aggregation, practice session selection, pace normalization, pit/in/outlap exclusions, anomalies, tire effects, wet/dry handling, and coverage for drivers with no representative qualifying lap. Do not silently drop such drivers or fill qualifying features with race laps. The current contract requires qualifying coverage for every included driver and at least three unique drivers. Practice may be absent if M3 supports missingness. Deliver source identifiers, row-level availability, retrieval timestamps and data/schema versions.

Readiness: no qualifying → **Awaiting qualifying data.** Missing required qualifying weather → **Awaiting qualifying-session weather.** Qualifying + weather → qualifying forecast allowed. Official final grid → grid-updated forecast allowed. Missing optional practice does not block supported inference. API errors/stale/partial data must be explicit failures, never fabricated live readiness or zero-valued replacements. Qualifying order is not a final starting grid.

Sources: **OpenF1** for practice, qualifying, qualifying-session weather, race results, laps and tire stints. **Jolpica** for historical grids. **FIA published final grid** for upcoming races. Include provenance, cache strategy, API failure behavior and calendar freshness.

## M2: historical tables and result adapter

- Driver-level table: race/driver identities, pre-cutoff features, availability timestamps and grid provenance, plus a separate podium target. Exclude labels/results from inference objects.
- Lap-level table: race/session/driver/lap identity, circuit, compound, tire age (laps), track temperature (°C), clean lap time (seconds), cleaning flags. Document joins/timestamp matching, compound normalization and missingness. Define clean laps: exclude pit/in/out, invalid, safety-car/red-flag and anomalous laps.
- Result adapter: `race_id`, exactly three unique driver IDs in actual finishing order, official status/source and `available_at_utc`. Compare only after official confirmation; corrections change the result view, never the saved forecast.
- Replace `demo.DEMO_RESULTS` with read-only result lookup. Its only fixture is fictional. Seeded 2/3 overlap is not a trained-model accuracy measurement.

## M3: podium inference

Replace `predictions.predict_podium(inputs, include_grid)` and return **three unique driver IDs** selected for the highest likelihood of a top-three finish in any order. The UI displays them alphabetically. Probabilities may be displayed only when supplied by an evaluated model; they are marginal podium probabilities, not a three-way softmax or finishing-position forecast.

Provide qualifying-only and grid-enabled paths (or a validated missing-grid pipeline). Qualifying mode must exclude grid features even when available. Deliver saved artifacts, preprocessing/encoders, feature order/schema/dtypes/units, missing/unseen-category behavior, category coverage, version identity, exact dependencies, seeds and a minimal inference example. Load only trusted artifacts and cache them; do not train/download on each Streamlit rerun.

Evaluation: chronological splits separated by race/season, test dates/sample sizes, per-race top-three set overlap (0–3), aggregate metrics, baselines and relevant classification/calibration metrics. Historical final grids belong only in the matching grid-enabled cutoff evaluation.

## M3: separate lap-time inference

Replace `predictions.estimate_lap(circuit, compound, tire_age_laps, track_temp_c)` returning `LapEstimate(seconds, test_mae_seconds, model_version)`. Deliver saved preprocessing/regressor, exact four-input contract, supported categories, numerical training ranges, unseen/out-of-range behavior, dependencies and a prediction example. Update demo UI choices/ranges from the agreed model metadata.

Report held-out **MAE in seconds** as typical test error, plus test dates/grouping, sample counts and optionally RMSE. Group correlated laps by event/session rather than splitting near-identical laps across train/test. Dataset-level MAE is not an individual prediction confidence interval. Leave error as `None` until measured.

## Cutoff and snapshot integrity

1. Cutoff must be timezone-aware UTC and strictly before official race start. Include only inputs available by cutoff. Use qualifying-session weather, never race weather/results/fastest race laps/later revisions.
2. `RaceInputs` carries no result labels. The prototype checks timestamps and finite inputs; M2 remains responsible for row-level availability and complete-field coverage.
3. Save an immutable snapshot with race identity, creation time, cutoff, qualifying/grid mode, model version, three driver IDs and exact input snapshot. Add source/data/artifact versions for real integration. Grid updates create new snapshots and preserve qualifying snapshots.
4. Join official results only afterward. Compute set overlap (0–3), independent of order. Never regenerate historical predictions after seeing a result.
5. Local JSON archives are ignored by Git and downloadable. A deployed shared app needs durable storage, concurrency handling, backups and retention. No official result ingestion or scheduler is connected yet.

## Integration acceptance examples

- Before qualifying → disabled forecast; missing qualifying weather → blocked.
- Practice absent → supported missingness or a clear model coverage error.
- Qualifying forecast followed by official grid → two independent snapshots.
- Input after cutoff or new inference after race start → rejected.
- Saved NOR/LEC/VER vs actual VER/NOR/PIA → 2/3, original prediction preserved.
- Invalid/unseen lap inputs → explicit validation, no silent default estimate.
