# F1 Podium Prediction — M3 ⇄ M1/M2 Interface Contract v1.0

Status: proposed contract for team sign-off. Version: 1.0.

## Responsibility boundaries
- M2 produces and verifies one-row-per-driver input tables, with only data known at forecast time.
- M3 validates, preprocesses, trains, evaluates, persists, and scores the models.
- M1 calls the stable prediction function and displays its output; M1 never refits models.

## Python API
```python
import pandas as pd

def predict_podium(race_data: pd.DataFrame, stage: str) -> pd.DataFrame:
    """Score every eligible entrant for one race; return deterministic descending scores."""
```

Stage values (exact strings): `post_qualifying`, `post_grid`.

Input: pandas DataFrame, exactly one race, one row per eligible driver, unique `(race_id, driver_number)`, with required fields below. The caller supplies all race entrants to be scored, not just the top 3. Never pass the actual race result in inference data.

### Required columns
| Field | Type | Rule | Stage |
|---|---|---|---|
| race_id | nonempty string | Stable ID, e.g. `2024_bahrain_gp`; same across stages | both |
| driver_number | integer | Unique within race | both |
| driver_name | nonempty string | Display value | both |
| qualifying_position | nullable integer | Official qualifying classification, normal GP qualifying (not sprint) | both |
| qualifying_gap_seconds | nullable float | Best valid qualifying lap minus fastest valid qualifying lap of the qualifying session, in seconds, >= 0 | both |
| practice_gap_seconds | nullable float | Best valid lap minus session-best lap in FP3, else latest practice prior to qualifying, >= 0 | both |
| qualifying_air_temp_c | nullable float | Median OpenF1 qualifying-session air temperature, Celsius | both |
| qualifying_track_temp_c | nullable float | Median OpenF1 qualifying-session track temperature, Celsius | both |
| qualifying_rainfall | nullable integer | 1 if any OpenF1 qualifying weather observation reports rainfall, else 0; null if not measured | both |
| grid_position | nullable integer | Verified final starting grid (including penalties); required for all starters at post-grid time | post_grid only |

**Feature definitions:** Qualifying gap uses the fastest valid lap recorded *anywhere* in the normal qualifying session, not Q3-only. Practice selector is consistent for all drivers in a race and excludes non-comparable pit-out/incomplete laps. For drivers with no valid lap/classification, use null, not made-up values. Qualifying and practice pace may vary with track evolution; document this limitation. Median weather conditions are shared across drivers in the same race. If FP3 doesn't exist, choose the latest preceding practice and record source metadata; missing practice stays null. OpenF1 provides air temperature, track temperature and rainfall via the *same* `/weather` endpoint.

Non-feature optional metadata, allowed but never fed to model by default: `meeting_key`, `qualifying_session_key`, `race_session_key`, `year`, `as_of_utc`, `data_source`, `team_name`. M2 should preserve keys and timestamps for traceability. All input fields must have been available at the declared forecast cutoff.

Pre-grid input MUST NOT contain actual final grid as a modeling feature. A `grid_position` column may be absent or null at `post_qualifying`. At `post_grid`, `grid_position` must be present and verified; do not silently substitute qualifying position.

### M3 output, always the same schema
| Field | Type | Meaning |
|---|---|---|
| race_id | string | Original race |
| driver_number | integer | Original driver number |
| driver_name | string | Original name |
| podium_probability | float | Binary classifier `predict_proba` for top-3 class (0..1), not guaranteed calibrated |
| predicted_rank | integer | Rank by descending score, tie-break ascending `driver_number` |
| is_podium_pick | boolean | True for exactly ranks 1, 2, 3 |
| stage | string | `post_qualifying` or `post_grid` |
| model_name | string | `logistic_regression` or `random_forest` (chosen model for that stage) |

Output contains exactly one row per input driver, sorted by `podium_probability` descending then `driver_number` ascending. The top three are *unordered podium selections*, not predicted finishing positions. Independent per-driver scores need not sum to 3. Reject fewer than three entrants, duplicate drivers, mixed races, invalid stage, unverified/missing post-grid positions, and missing required columns with descriptive errors. No model result should silently be reported if the model artifact is missing; a clearly labeled *mock adapter* may be used separately for UI development.

### Target for training only
`is_podium_actual`: integer 1 when the driver is classified in finishing position 1, 2, or 3 in the official **Grand Prix race** result; 0 otherwise (DNF, DNS, DSQ, positions 4+). If status or classification is ambiguous, flag for M2 review rather than quietly impute. Exclude this and all post-race results from inference features. Keep sprint and Grand Prix results separate.

### Algorithm and evaluation
- Two stages, each comparing LogisticRegression vs shallow RandomForestClassifier using the same historical race partitions and same target; four candidate pipelines total.
- `Pipeline` and `ColumnTransformer`: median imputers for nullable numerical features, appropriate scaling for Logistic Regression; imputation without necessarily scaling for Forest; fit transformers only on training races.
- Select each stage's winner by held-out mean correct top-3 selections per race, then exact 3/3 race rate; document ties and secondary classification metrics. No tuning on final test races; use chronological validation within training history for model choice, then evaluate once on the final later-race test period.
- Use temporally ordered complete-race partitions, never split drivers from one Grand Prix across subsets. Show number and date range of races in each partition. Report baseline top three *qualifying positions* (post_qualifying) or top three *final grid positions* (post_grid), mean correct picks out of 3, exact-set 3/3 success rate, and one real disagreement/miss; report precision/recall or other classification metrics as supporting evidence.
- No performance metrics may be claimed from one historical race; one race is only a data-contract and inference smoke test.
- Save pipelines with joblib and a metadata JSON recording contract version, stage, chosen model, feature list, training race cutoff, and library versions. Reproduce same output between evaluation and M1-facing call; pin dependencies.

## M1 UI-development synthetic example (not trained results)
```python
import pandas as pd
sample = pd.DataFrame([
    {"race_id":"demo_gp", "driver_number":11, "driver_name":"Driver A", "qualifying_position":1, "qualifying_gap_seconds":0.0, "practice_gap_seconds":0.12, "qualifying_air_temp_c":26.0, "qualifying_track_temp_c":38.0, "qualifying_rainfall":0, "grid_position":1},
    {"race_id":"demo_gp", "driver_number":22, "driver_name":"Driver B", "qualifying_position":2, "qualifying_gap_seconds":0.14, "practice_gap_seconds":0.22, "qualifying_air_temp_c":26.0, "qualifying_track_temp_c":38.0, "qualifying_rainfall":0, "grid_position":3},
    {"race_id":"demo_gp", "driver_number":33, "driver_name":"Driver C", "qualifying_position":3, "qualifying_gap_seconds":0.23, "practice_gap_seconds":0.32, "qualifying_air_temp_c":26.0, "qualifying_track_temp_c":38.0, "qualifying_rainfall":0, "grid_position":2},
    {"race_id":"demo_gp", "driver_number":44, "driver_name":"Driver D", "qualifying_position":4, "qualifying_gap_seconds":0.42, "practice_gap_seconds":0.55, "qualifying_air_temp_c":26.0, "qualifying_track_temp_c":38.0, "qualifying_rainfall":0, "grid_position":4},
])
```
The production function requires trained artifacts. Until then, M1 may use separate, explicitly labeled mock scores (not represented as actual trained predictions).
