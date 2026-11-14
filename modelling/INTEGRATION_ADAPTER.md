# Dashboard integration adapter

`integration_adapter.py` translates requests only. It never trains, fetches data,
writes artifacts, supplies fallback predictions or changes approval decisions.
M1 remains unchanged and is not connected automatically.

## Imports and interfaces

The existing M3 modules use sibling imports. Configure the repository root and
`modelling/` on the application's Python import path, then import
`integration_adapter`. Do not load a second copy under a different module name.
The modelling pytest configuration supplies both paths for tests.

```python
predict_podium(inputs: RaceInputs, include_grid: bool = False, *, context: PodiumContext) -> PodiumResult
estimate_lap(circuit: str, compound: str, tire_age_laps: int, track_temp_c: float,
             *, context: LapContext) -> LapResult
```

There is deliberately no injectable inference callback in either public API.
Tests monkeypatch module functions; application callers use the existing public
`m3.predict_podium` and `lap_model.predict_lap_time`, including all their artifact
and evidence checks. Exceptions propagate; callers must handle missing artifacts
as well as validation errors. Only trusted local artifacts/evidence are supported.

## Podium input and output

`inputs` is the unchanged M1 dataclass. `include_grid` must be a boolean and maps
to `post_grid` when true, otherwise `post_qualifying`. M1 timestamp, weather,
driver-field and grid validation runs first. Qualifying mode omits grid entirely.

`PodiumContext` requires all of:

| Field | Schema / meaning |
|---|---|
| handoff_path | Path to the approved M2 stage manifest |
| drivers | DataFrame with exactly ordered columns `dashboard_driver_id,driver_id,driver_number,qualifying_position` |
| qualifying_air_temp_c | Explicit finite number or M2-reviewed null |
| qualifying_gap_definition | `best_valid_all_segments_minus_session_best_seconds` |
| practice_gap_definition | `best_valid_selected_common_practice_minus_session_best_seconds` |
| reviewer | Named reviewer accountable for translation semantics and identity mapping |
| reviewed_at_utc | Timezone-aware review timestamp |
| grid_verified | Explicit M2 attestation; must be true for post-grid |

Each dashboard ID, canonical M2 driver ID and race-specific driver number must be
unique, and mappings must cover the exact dashboard field. Canonical IDs must
match the approved hashed crosswalk. Display names and supplementary feature
values must match the approved feature table. Race ID, UTC start and stage cutoff
must match the handoff. No fuzzy joins, number guesses, synthetic classifications
or null-to-zero substitutions occur. The two definition strings are explicit
review attestations, not automatic proof of semantics; reviewers must establish
their truth before calling. The handoff still supplies source lineage and hashes.

Renames: `qualifying_delta_s -> qualifying_gap_seconds`,
`practice_delta_s -> practice_gap_seconds`; null practice remains null. Rainfall
becomes integer 0/1. All other feature names follow the M3 stage schema.

```python
context = PodiumContext(
    handoff_path=reviewed_stage_path,
    drivers=reviewed_mapping,
    qualifying_air_temp_c=reviewed_air_temperature,
    qualifying_gap_definition='best_valid_all_segments_minus_session_best_seconds',
    practice_gap_definition='best_valid_selected_common_practice_minus_session_best_seconds',
    reviewer=reviewer_name, reviewed_at_utc=review_time,
    grid_verified=verified_final_grid,
)
result = predict_podium(inputs, include_grid, context=context)
picks = result.picks
```

`PodiumResult` contains three unique dashboard-ID strings in alphabetical display
name order (ID breaks name ties), the persisted `model_version`, and `evidence`
containing handoff ID/hash, source hashes and assumption decisions. Picks follow
the actual M3 selection flags. The entire result field, rankings, probabilities,
tie policy, stage and model identity are validated before conversion.

## Lap input and output

`LapContext` requires `row`, `mode`, `evidence_path`, `scenario_provenance`,
`circuit_display_name`, and `tyre_age_convention`. The last must explicitly be
`completed_laps_before_target`, matching M2 A1; no age adjustment is inferred.
The display name must equal the scalar circuit argument; the explicit row's
canonical circuit is validated against M2's reviewed context. M1 must obtain this
display-name-to-canonical-ID binding from its reviewed input provider.

`row` must contain exactly these ten keys, including explicit nullable fields:

```text
example_id,race_id,session_key,driver_number,driver_name,driver_id,circuit_id,
lap_number,prediction_time_utc,weather_observed_at_utc
```

The other three ordered M3 columns come from scalars: `compound`,
`tire_age_laps -> tyre_age_laps`, `track_temp_c -> track_temperature_c`.
Historical session/lap/weather values are required; scenario nulls follow M3's
rules. `mode` is exactly `historical` or `scenario`. `evidence_path` supplies
`m2_handoff_path` for historical scoring or `m2_context_path` for scenarios.
`scenario_provenance` is explicitly None for historical requests or the complete
example-ID-keyed provenance dictionary for scenarios. Nothing selects a driver,
weekend, session or canonical circuit on the user's behalf.

```python
context = LapContext(
    row=explicit_reviewed_identity_and_timing,
    mode='scenario', evidence_path=approved_context_path,
    scenario_provenance={example_id: {
        'compound': 'user_scenario', 'tyre_age_laps': 'user_scenario',
        'track_temperature_c': 'user_scenario',
    }},
    circuit_display_name=selected_circuit,
    tyre_age_convention='completed_laps_before_target',
)
result = estimate_lap(selected_circuit, compound, age, temperature, context=context)
estimate = result.estimate  # unchanged M1 LapEstimate type
```

`LapResult` retains `estimate`, `is_hypothetical`, `support_status`, `evidence`
(handoff/context ID/hash and source hashes), and complete validated
`artifact_metadata`. `estimate.seconds` and `.model_version` come from M3.
`test_mae_seconds` remains None: choosing a representative held-out metric and
disclosing its supported population is an unresolved product/evaluation decision.
Full evaluation remains in artifact metadata. MAE is never a confidence interval.

## Approval and M1 integration dependencies

Both tasks validate the evidence before inference and then call the original
public M3 API, which repeats its own safeguards. Context review strings do not
replace `approved_for_modeling=true`, reviewer/time, hashed files, source lineage,
resolved quality issues and reviewed identities. A caller cannot bypass a missing,
legacy, corrupt or incompatible artifact. No production artifacts exist yet.

M1 must later supply these contexts through a reviewed provider, use `.picks` or
`.estimate`, and retain the accompanying metadata. It must replace hardcoded demo
snapshot/version information, preserve qualifying and grid snapshots separately,
and display hypothetical clean-practice scope and numeric extrapolation status.
Discarding the result wrapper loses necessary disclosures. Its current four-input
lap form needs explicit driver/weekend/context selection. Categories and ranges
must follow artifact metadata rather than demo constants. Cache integration is
still open: this adapter intentionally retains M3's current per-call checks and
does not cache evidence or artifacts that could have changed.

Other unresolved decisions: reviewed pace-definition agreement; M1's stricter
missing-qualifying policy; live context provisioning; error presentation; exact
dependency deployment; and safe version-aware caching. M2 must deliver approved
stage packages and the historical/scenario lap evidence specified by the existing
contracts. Synthetic tests confer no real-data approval or performance claim.

## Verification

From `modelling/`, run `.venv\Scripts\python.exe -B -m pytest -q`.
Adapter tests use temporary synthetic evidence under `.test-work/` and stub
inference; existing suites fit only synthetic models under `.test-work/`.
Run dashboard tests from the repository root with the same interpreter and
`-B -m pytest -q -p no:cacheprovider tests`.
