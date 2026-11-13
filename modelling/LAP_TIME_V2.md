# Contract v2 practice lap-time implementation

`lap_model.py` implements ordinary LinearRegression for conditional clean normal
practice flying-lap duration. It is independent of the Random Forest podium task.
No real-data model has been trained. The existing five-race pilot is not an
approved lap-training dataset.

The implemented public signature is `predict_lap_time(lap_data)`. Mode is supplied
in `lap_data.attrs['mode']` as `historical` or `scenario`, rather than as the second
argument proposed in CONTRACT_v2.md. The contract document remains unchanged.
Input columns must exactly match the order in `lap_model.INPUT_COLUMNS`; outputs
follow `lap_model.OUTPUT_COLUMNS` and preserve input order.

```python
from lap_model import train_lap_model, predict_lap_time

# Features and labels are separate DataFrames from an approved M2 package.
features.attrs['mode'] = 'historical'
features.attrs['m2_handoff_path'] = 'reviewed/handoff.json'
evaluation = train_lap_model(features, labels)
predictions = predict_lap_time(features)

# Scenarios require reviewed identities/scope and explicit assumption provenance.
scenario.attrs['mode'] = 'scenario'
scenario.attrs['m2_context_path'] = 'reviewed/context.json'
scenario.attrs['scenario_provenance'] = {
    'example-1': {
        'compound': 'user_scenario',
        'tyre_age_laps': 'user_scenario',
        'track_temperature_c': 'user_scenario',
    }
}
# Set weather_observed_at_utc to null for an assumed temperature.
hypothetical = predict_lap_time(scenario)
```

CSV files do not preserve DataFrame attrs. Callers must restore them explicitly.
Scenario provenance keys must match every example_id. Measured scenario weather
uses `openf1` provenance and requires eligible reviewed weather evidence.

`lap_handoff.py` validates hashed evidence, exact historical features and separate
targets, reviewed driver/circuit crosswalks, field lineage and pre-race cutoffs.
Historical evidence includes practice session identity, clean-lap decisions,
unique stint mapping, completed tire age, lap/target availability and backward
weather matching. M2 must explicitly resolve A1/A2/A3, including weather freshness
and supported compounds. Missing evidence remains an error. Synthetic packages in
`lap_synthetic.py` illustrate the format but do not constitute real M2 approval.

The five model features are compound, tyre_age_laps, track_temperature_c,
circuit_id and driver_id. Preprocessing uses one-hot encoding with the first
sorted training category dropped, and StandardScaler on numeric features. No
missing inputs or targets are imputed. Unknown categorical values are rejected;
numeric extrapolation is flagged. Nonpositive/nonfinite predictions are rejected.

Training splits complete weekends chronologically 60/20/20, validates the fixed
model, then refits on train plus validation before final evaluation. A minimum of
five groups is a mechanical split guardrail, not evidence of statistical
sufficiency; real-data sufficiency still requires an evaluation plan and M2 review.
Reports include MAE, RMSE, median absolute error, signed bias, R-squared, weekend
macro metrics, category breakdowns, unsupported coverage and a prior-training-lap
baseline with circuit-median fallback. Held-out targets never define that baseline.

Production artifacts default to `artifacts/v2/lap_time/`: model joblib, matching
metadata and evaluation JSON. Metadata records schema, domains, ranges, versions,
source hashes, preprocessing and partition cutoffs. Incompatible or corrupted
artifacts fail explicitly. Only trusted local joblib artifacts should be loaded.

Run the self-contained synthetic demonstration from `modelling/`:

```powershell
.venv\Scripts\python.exe -B lap_smoke.py
.venv\Scripts\python.exe -B -m pytest -q
```

The demo writes evidence, artifacts and `smoke_result.json` only under a unique
`.test-work/lap_smoke_*` directory. Its exact linear synthetic target can produce
near-zero errors; these are software checks, not historical performance evidence.
Scenarios are labeled hypothetical clean practice laps. They do not establish
Grand Prix race pace, strategy or podium probabilities.
