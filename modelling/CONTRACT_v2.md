# F1 prediction interface contract v2.0

Status: PROPOSED interface specification. The two-model architecture is approved;
the M2 assumptions and evidence requirements below remain open. This document
does not certify data or describe functionality already implemented.

Effective implementation: not yet migrated. CONTRACT.md v1.0 remains the unchanged
reference for the existing code and five-race verification snapshot. V2 must not
be advertised as implemented until its code, tests and M2 handoff are completed.

## 1. Scope and responsibility

| Task | Production model specified by v2 | Output |
|---|---|---|
| Podium, post_qualifying | RandomForestClassifier | Per-driver podium probability and three unordered picks |
| Podium, post_grid | RandomForestClassifier | Same output, with verified final grid as an additional feature |
| Clean practice flying-lap time | LinearRegression | Conditional lap duration in seconds |

The two tasks are independent. Lap-time outputs are not inputs to the podium
classifier. Linear Regression is not a podium classifier. Logistic Regression is
outside the intended v2 production architecture; its existing code remains
unchanged until a separate implementation task is authorized.

- M2 owns source verification, race/driver/circuit identity, eligible entrants,
  clean-lap decisions, cutoff evidence, source conflicts, labels and reviewed
  handoff tables. Missing evidence must remain unresolved.
- M3 owns schema validation, train-only preprocessing, model fitting, temporal
  evaluation, artifacts, supported-input checks and reproducible scoring. M3
  cannot turn a successful smoke test or an edited checklist into M2 approval.
- M1 supplies contract inputs and their handoff/scenario context, calls persisted
  models and displays the correct task/mode. M1 never fits or refits models.

Only OpenF1 and Jolpica are approved historical data sources. OpenF1 is primary
for detailed laps, tires and weather. Jolpica may supplement or verify historical
qualifying classification, starting grids and Grand Prix results. No Jolpica
integration or data download is part of this contract-only change.

The five-race pilot, original contract, verification decisions, raw caches,
existing CSVs and artifacts are preserved. V2 introduces no automatic expansion
to additional races or seasons.

## 2. Common conventions

- UTC timestamps are timezone-aware ISO 8601 values. Naive/local timestamps are
  rejected until M2 supplies a documented conversion.
- String identifiers are nonempty and stable; numbers and temperatures are finite.
  Empty source values remain null, never strings such as "unknown" in numeric
  columns. Integer columns must have integral values.
- race_id is the existing canonical ID, for example 2024_bahrain_gp.
  driver_number identifies a driver within a race, not across all history.
- driver_id is a stable M2 canonical person identifier, independent of race number
  and spelling. circuit_id is an M2 canonical circuit/layout identifier.
- Forecast time means the information cutoff, not the later API retrieval time.
  An event timestamp alone does not prove publication/availability at that time.
- Model feature columns are explicitly allowlisted. Labels, results, metadata,
  raw sector times, source identifiers and review decisions are never implicitly
  included because they happen to be present in a file.
- Exported feature tables have exactly the schema for their task/stage below.
  Provenance, cutoffs, quality decisions and training targets are separate.
- Each prediction batch is atomic: invalid rows are identified in a descriptive
  error rather than silently dropped or partially scored.

## 3. Sources, identity matching and conflicts

### 3.1 Proposed field ownership

These are canonical field mappings and source responsibilities, not implemented
Jolpica API adapters. Exact Jolpica transport/field mapping will be documented and
tested when integration is separately authorized.

| Canonical field or concept | Primary supplier | Supplement/verification and restriction |
|---|---|---|
| race_id, race/driver/circuit crosswalks | M2 curated mappings using OpenF1 session/meeting/driver/circuit evidence | Jolpica season/round, circuit and driver identifiers may corroborate; no fuzzy-name-only join |
| driver_number, driver_name, eligible pre-race roster | OpenF1 normal qualifying driver records, verified by M2 | Jolpica qualifying/entry evidence may verify; race outcomes cannot retrospectively select entrants |
| qualifying_position | OpenF1 normal GP qualifying session_result | Jolpica normal qualifying classification may supplement/verify after M2 adjudication |
| qualifying_gap_seconds | Derived from valid OpenF1 normal qualifying laps across all segments | Jolpica Q1/Q2/Q3 times may verify; no automatic replacement from a single segment or qualifying position |
| practice_gap_seconds | Derived from valid OpenF1 selected practice laps | No Jolpica replacement or fabricated pace |
| qualifying_air_temp_c, qualifying_track_temp_c, qualifying_rainfall | OpenF1 qualifying weather | No Jolpica replacement |
| grid_position | OpenF1 starting_grid associated with normal qualifying | Jolpica GP starting grid may supplement/verify penalties and final classification; finality/cutoff still require evidence |
| is_podium_actual, result/status audit | OpenF1 normal GP race session_result | Jolpica normal race results/status may supplement/verify; training labels only |
| compound | OpenF1 stints.compound | User-supplied assumption only in scenario mode |
| tyre_age_laps | Derived from OpenF1 stints.tyre_age_at_start and lap/stint numbering | User-supplied assumption only in scenario mode; convention requires M2 confirmation |
| track_temperature_c | Latest eligible OpenF1 weather.track_temperature at cutoff | User-supplied assumption in scenario mode; never silently replaced by qualifying/session median |
| lap_time_actual_seconds | OpenF1 laps.lap_duration for an M2-approved clean practice lap | Target only; no source substitution |
| prediction_time_utc and field availability | M2 verified cutoff/provenance for historical rows | Scenario time is the time assumptions are entered; not a claim of an observed future lap |

User scenario assumptions are not a third historical dataset source.

### 3.2 Matching rules

M2 maintains versioned crosswalks outside ML feature tables:

| Mapping | Required canonical columns |
|---|---|
| Race | race_id, season, round, circuit_id, openf1_meeting_key, openf1_qualifying_session_key, openf1_race_session_key, jolpica_race_key, review_status |
| Driver within race | race_id, driver_id, driver_number, driver_name, openf1_driver_number, jolpica_driver_id, review_status |
| Circuit/layout | circuit_id, openf1_circuit_key, jolpica_circuit_id, layout_version, review_status |

Jolpica identifiers may be null until integration and matching are verified.
review_status is verified, corrected or unresolved. No crosswalk is approved
merely because identifiers have been filled in.

Race matching uses season/round plus circuit and dated weekend evidence,
accounting for timezone changes and rescheduling. Country or event-name equality
alone is insufficient. Use one canonical GP meeting; explicitly exclude sprint,
sprint qualifying and shootout sessions. Session selection must identify normal
Qualifying and Race, and verify the same OpenF1 meeting.

Driver matching uses the reviewed person crosswalk plus race-specific numbers.
Names/abbreviations can corroborate but cannot resolve ambiguous substitutions.
Join practice, qualifying, grid and labels by session/meeting and canonical
race/driver keys, never row order. Circuit layout changes require a reviewed
mapping; do not treat different layouts as interchangeable without a decision.

Preserve all entrants eligible at each forecast cutoff. A later DNS/DNF/DSQ can
affect the training label, not retrospectively remove a previously eligible row.

### 3.3 Conflict policy and provenance

OpenF1 is the default primary source, not an automatic winner in a disagreement.
For disagreement in classification, status, grid, identity or timing:

1. Preserve both raw records and field values with retrieval times and source IDs.
2. Check race/session identity, normal-vs-sprint scope, units, status semantics,
   penalties, revision/publication time and cutoff.
3. M2 selects a value with documented evidence, or leaves the field unresolved.
4. No averaging, silent overwrite, fuzzy identity guess, qualifying-to-grid
   substitution or future correction backfill is allowed.
5. A supplemental value is usable only if its identity, meaning and availability
   at the relevant cutoff are verified. Corrected historical final results may
   define labels; they cannot silently revise earlier forecast features.

Record field lineage separately with these exact columns:

task, row_key, field_name, selected_source, source_record_refs, derived_from,
observed_at_utc, available_at_utc, retrieved_at_utc, review_status, reviewer,
reviewed_at_utc, resolution_notes.

task is podium or lap_time. row_key is a canonical JSON key object: race_id plus
driver_number for podium, or example_id for lap time. selected_source is openf1,
jolpica, derived, or user_scenario. source_record_refs is a JSON list of source,
cached relative path, record key and SHA-256 references. derived_from is a JSON
list of upstream field references. Unknown timestamps remain null and block
claims of verified historical availability. Scenario provenance is explicitly
hypothetical, not M2 certification of a future observation.

An unresolved non-null value is not ready for modeling. Legitimate absence
(e.g. no valid qualifying time) can be verified as a null. Pit-lane/zero grid codes,
ambiguous classifications and conflicting statuses require M2 resolution; do not
invent a numbered grid slot to satisfy validation.

## 4. Podium task: schemas and timing

Proposed retained API:

    predict_podium(race_data: pd.DataFrame, stage: str) -> pd.DataFrame

stage is exactly post_qualifying or post_grid. One call contains exactly one race,
one row per eligible driver, at least three drivers, and unique
(race_id, driver_number). The following is the exact exported input schema.

| Column | Type | Definition |
|---|---|---|
| race_id | nonempty string | Same canonical race ID at both stages |
| driver_number | positive integer | Unique within race |
| driver_name | nonempty string | Display name, not a model feature |
| qualifying_position | nullable positive integer | Official normal GP qualifying classification, not sprint or final grid |
| qualifying_gap_seconds | nullable nonnegative float | Driver best valid qualifying lap anywhere in Q1/Q2/Q3 minus the session fastest valid lap |
| practice_gap_seconds | nullable nonnegative float | Best valid lap in the selected common practice minus that session's fastest valid lap |
| qualifying_air_temp_c | nullable float | Median of eligible qualifying-session air-temperature observations |
| qualifying_track_temp_c | nullable float | Median of eligible qualifying-session track-temperature observations |
| qualifying_rainfall | nullable integer, 0 or 1 | Any eligible qualifying observation reports rainfall; null if unmeasured |
| grid_position | positive integer at post_grid only | M2-verified final penalized starting position for every eligible starter |

The post_qualifying export has the first nine columns only. For compatibility,
its in-memory API may tolerate an absent or entirely null grid_position column;
a populated final grid must never become a post_qualifying model feature.
The post_grid export has all ten columns. No label/metadata columns are exported
as model inputs. Metadata is delivered in the handoff described below.

Feature list for post_qualifying: qualifying_position, qualifying_gap_seconds,
practice_gap_seconds, qualifying_air_temp_c, qualifying_track_temp_c,
qualifying_rainfall. post_grid adds grid_position. Driver/race identifiers and
display names are not podium model features.

Select FP3 when present before normal qualifying, otherwise the latest preceding
practice for the entire race. Record that selection outside features. Missing
practice stays null. Exclude incomplete, pit-out, pit-in and invalid/deleted laps;
resolve reinstatements. Explicit absence of valid qualifying segment times means
a null gap, even if a complete-looking in-lap exists. Track evolution limits
comparability and must be disclosed. Weather aggregates are common to all drivers.

For post_qualifying, M2 declares a verified cutoff after all included qualifying
information was available; scheduled session end is only a candidate timestamp.
For post_grid, M2 declares a verified final-grid publication/availability cutoff
before the GP race starts. Include only observations/results known by that stage.
No race laps, race telemetry, finishing results, points, future penalties or later
weather are allowed as podium predictors. Historical labels may be attached only
inside the training/evaluation workflow, never in an inference call.

Missing qualifying/practice/weather values are permitted only when M2 has
verified the absence and recorded a reason. Median imputation is fitted on
training races only. If an entire required numeric feature has no training
observations, stop for an explicit modeling decision rather than silently filling
a fabricated constant. Missing/unverified grid blocks post_grid scoring;
qualifying position is never a fallback.

Exact output schema, unchanged in shape from v1:

| Column | Type | Definition |
|---|---|---|
| race_id | string | Input race |
| driver_number | integer | Input driver |
| driver_name | string | Input display name |
| podium_probability | float, 0..1 | Random Forest top-three class probability, not guaranteed calibrated |
| predicted_rank | integer, 1..N | Descending probability, tie-break ascending driver_number |
| is_podium_pick | boolean | True exactly for ranks 1, 2 and 3 |
| stage | string | post_qualifying or post_grid |
| model_name | string | Always random_forest in v2 |

Return every input driver, sorted by descending probability then ascending driver
number. Picks are an unordered podium set, not predicted finishing positions.
Independent probabilities need not sum to three.

Separate training-label table, exact columns:
race_id (string), driver_number (integer), is_podium_actual (integer 0/1).
Use one on official GP finishing positions 1-3, zero otherwise, including
DNF/DNS/DSQ under the agreed status interpretation. Ambiguous/missing labels stay
null in draft data and block affected race training until M2 resolves them.
Do not split a race's eligible drivers across partitions.

The existing explicit grid_verified=True DataFrame attestation remains necessary
for post_grid, but is not sufficient by itself: production v2 also requires a
matching approved M2 handoff and hashes. CSV files do not preserve DataFrame attrs.

## 5. Lap-time task: historical examples versus scenarios

Initial empirical scope: clean practice flying laps only, from normal practice
sessions in reviewed GP weekends. Qualifying, sprint and race lap targets are
outside this initial scope. Do not mix these regimes under a practice-lap label.

A historical example is a real completed practice lap whose actual duration is
available only as a later target. Reconstruct the inputs as of its lap-start
prediction cutoff, then audit the target/clean-lap status separately. Historical
records without adequate timing, stint mapping or validity evidence remain
draft/quarantined, not silently promoted to leakage-free training examples.

A pre-race scenario is a hypothetical clean practice flying lap conditional on
the entered compound, tire age, temperature, circuit and driver. It need not
correspond to an observed lap, has no actual target and is never a training row.
It is not a prediction of the GP race's actual next lap, average race pace,
strategy, podium probability or future track temperature.

Proposed new API (not implemented):

    predict_lap_time(lap_data: pd.DataFrame, mode: str) -> pd.DataFrame

mode is exactly historical or scenario; a batch has one mode. historical is for
artifact-backed retrospective scoring/evaluation with as-of verified inputs;
scenario is for user-entered hypothetical conditions. Both use the same learned
regression and distinct provenance requirements.

### 5.1 Exact input schema

Every batch has these thirteen columns in this order:

| Column | Type | Rule |
|---|---|---|
| example_id | nonempty string | Unique within batch; historical dataset IDs are globally unique within its version |
| race_id | nonempty string | Reviewed weekend ID; for scenarios, the intended known weekend |
| session_key | nullable positive integer | Historical: exact normal practice session required. Scenario: null or known intended practice session |
| driver_number | positive integer | Race-specific metadata; must agree with driver_id crosswalk |
| driver_name | nonempty string | Display only |
| driver_id | nonempty string | Stable reviewed person identifier; categorical model feature |
| circuit_id | nonempty string | Reviewed circuit/layout identifier; categorical model feature |
| lap_number | nullable positive integer | Historical: observed target lap required. Scenario: optional planned lap, not a model feature |
| prediction_time_utc | UTC timestamp | Historical: target lap start. Scenario: time assumptions were entered, before intended GP race start |
| compound | categorical string | SOFT, MEDIUM, HARD, INTERMEDIATE or WET; artifact must support the specific observed category/regime |
| tyre_age_laps | integer >= 0 | Completed tire laps immediately before the target flying lap; see assumption A1 |
| track_temperature_c | finite float | Historical as-of observation or explicit scenario assumption |
| weather_observed_at_utc | nullable UTC timestamp | Historical: required observation timestamp. Scenario: null for assumed temperature, or actual observation time if using known measured weather |

Model features are exactly compound, tyre_age_laps, track_temperature_c,
circuit_id and driver_id. All other columns are identifiers, display or timing
validation fields. No target, sector time, race outcome, future lap/stint length
or review decision is a model feature.

Use ordinary scikit-learn LinearRegression with train-fitted preprocessing:
categorical one-hot encoding with a documented reference-category convention,
and any numeric scaling fitted only on training partitions. Do not substitute
Logistic Regression, RandomForestRegressor or another algorithm for this task.
Circuit/driver IDs are categories, not ordinal numeric values.

Unknown circuit/layout, driver or compound categories are unsupported and must
raise a descriptive error rather than silently use an intercept/zero encoding.
Record the supported domains and per-category training coverage in metadata.
Different track layouts cannot inherit support without an M2 mapping decision.

Essential lap inputs are not nullable except where explicitly shown. Reject
missing/invalid inference inputs. Quarantine missing historical inputs/targets
with an exclusion reason; never invent tire age, compound, weather or lap time.
Numerical extrapolation within otherwise supported categories must be flagged
in the output and UI; it is not evidence of multivariate similarity.

### 5.2 Tire-age and weather assumptions requiring M2 confirmation

A1 — Proposed tire-age convention:

    tyre_age_laps = tyre_age_at_start + (target_lap_number - stint_lap_start)

The value is completed laps before starting the target lap. The first numbered
lap in a stint has the reported starting age; do not add one merely because the
target lap will complete another lap. Match by session, driver and a unique stint
interval. Do not reset reused tires to zero. M2 must confirm OpenF1 numbering,
pit-out lap counting, cross-session tire reuse and off-by-one behavior using
cached evidence. Ambiguous/overlapping/missing stint mappings stay unresolved.

Completed-history lap_end can help audit a historical join; neither lap_end,
final stint length nor the time of a later pit stop can be a predictor or prove
that stint membership was known at lap start. Stint records lacking availability
timestamps need independent M2 provenance or an explicit retrospective-only flag.

A2 — Proposed historical weather rule:

Choose the latest observation from the same practice session with
weather_observed_at_utc <= prediction_time_utc, whose availability by the cutoff
M2 has verified. Proposed maximum observation age is 120 seconds. This value is
a pending M2/team policy, not a measured property of the cache; it must be
confirmed and recorded in the approved handoff/artifact before deployment.
If no eligible fresh observation exists, quarantine/reject the historical row.

Do not use nearest-in-time matching that can select a future observation,
forward-looking interpolation, the target lap's mean weather, qualifying weather
for a practice lap, or a full-session median. Conflicting observations with the
same timestamp need M2 resolution. Missing lap-start timestamps cannot be guessed.

Scenario temperature may be explicitly assumed; weather_observed_at_utc is then
null and provenance is user_scenario. If the scenario presents a temperature as
measured, it must satisfy the same as-of and freshness policy. A future weather
assumption is not an observed OpenF1 value and must be labeled hypothetical.

A3 — Clean-lap validity and supported regimes:

M2 must verify complete timed practice flying laps, excluding pit-in/out,
incomplete, invalid/deleted laps and non-comparable laps affected by session
interruptions/flags or other documented conditions. Resolve reinstatements and
retain an exclusion audit. M2 must confirm which wet/dry regimes and compound
categories the first artifact supports; an allowed schema value alone is not
proof that a model was trained/validated for that regime.

Later clean-lap adjudication can determine training-target eligibility, but it
must not be a predictor or be described as known at lap start. Report evaluation
as conditional on the approved clean-lap subset, not as accuracy on all laps.

### 5.3 Separate targets and exact output schema

Historical label table has exactly:
example_id (nonempty string), lap_time_actual_seconds (finite float > 0).

There is one target per approved historical example. Never impute a target;
do not attach historical targets or scenario outcomes to inference inputs.
Scenario rows must not appear in this label table.

Output preserves input row order and has exactly these thirteen columns:

| Column | Type | Meaning |
|---|---|---|
| example_id | string | Input key |
| race_id | string | Input weekend |
| driver_id | string | Canonical driver context |
| driver_number | integer | Race-specific driver number |
| driver_name | string | Display name |
| lap_number | nullable integer | Observed/planned input lap |
| mode | string | historical or scenario |
| prediction_time_utc | UTC timestamp | Input cutoff/assumption-entry time |
| predicted_lap_time_seconds | finite float > 0 | Conditional clean-practice lap duration |
| model_name | string | Always linear_regression |
| model_version | nonempty string | Persisted artifact identifier |
| is_hypothetical | boolean | True for scenario; false for historical |
| support_status | string | within_training_numeric_ranges or numeric_extrapolation |

support_status compares numeric age/temperature to the artifact's training bounds;
it is not a confidence interval or guarantee of joint support. Unsupported
categories fail rather than receiving that flag. Nonfinite/nonpositive regression
outputs are explicit unsupported-prediction errors, not silently clipped values.
Prediction intervals are not part of this contract.

## 6. Leakage prevention and evaluation

Use chronological, complete race-weekend groups for both tasks. All practice
laps, drivers and sessions from the same weekend belong to one partition. Never
randomly split laps, drivers or stints across train/validation/test, even if the
lap count appears large. Report weekend/session/row counts, date ranges,
exclusions, supported-category coverage and baseline coverage.

Fit encoders, imputers, scaling and model parameters on training groups only.
Any model/hyperparameter/policy selection uses earlier chronological validation;
freeze choices before the final later-period test. If refitting on train plus
validation, record the new training cutoff and keep final test untouched.
Both podium stages use the same race partitions. Use the same outer weekend
boundaries for lap comparisons where their eligible data overlap.

No final-test information may choose features, categories, thresholds, outlier
rules or tire/weather policies. M2 validity rules and handoff versions must be
declared, not adjusted merely to improve reported errors. Historical target
auditing is separate from as-of feature construction.

### 6.1 Podium evaluation

- Primary: held-out mean correct unordered top-three selections per race (0-3)
  and exact-set 3/3 rate.
- Baselines: top three qualifying positions for post_qualifying; top three final
  verified grid positions for post_grid. Disclose missing-baseline values and
  do not invent positions.
- Supporting: average precision/PR-AUC, Brier score or calibration diagnostics,
  and documented threshold-based precision/recall. Probability calibration, if
  introduced, must use training/validation only.
- Report a real disagreement/miss when present; do not fabricate one.
- Random Forest is the selected architecture, not a winner over lap regression.
  Retain shallow-forest defaults initially; any tuning must respect the above.

### 6.2 Lap-time evaluation

- Primary: MAE in seconds.
- Supporting: RMSE, median absolute error, signed mean error and R-squared where
  defined. Report per-weekend macro averages and lap-weighted aggregates.
- Break down by circuit/layout, driver, compound, tire-age range, session and
  wet/dry regime when sample sizes permit; show counts and unsupported rows.
- Compare against a simple baseline using only prior eligible completed lap
  times available at each cutoff, with an explicit fallback/coverage policy.
  No held-out target or full-session average may define its own baseline.
- Held-out circuits/drivers absent from training are unsupported under this
  initial categorical model; report coverage and abstentions, not an apparently
  accurate metric on an undisclosed surviving subset.
- Scenario outputs have no actual targets and no measured-accuracy claims.

Five weekends, each at a different circuit, cannot establish reliable generality
at previously observed circuits or a broad next-race lap predictor. More laps are
not more independent race groups. The existing podium minimum of ten reviewed
races remains unchanged; regression data sufficiency and category support require
an explicit M3 evaluation plan after M2 approval. No threshold is relaxed and no
additional collection or training is authorized by this document.

## 7. Handoff, artifacts and M1 integration

### 7.1 M2 handoff

Supply feature tables, separate labels when training, crosswalks and field
lineage as above, plus a versioned handoff JSON with these required top-level keys:

| Key | Type and meaning |
|---|---|
| handoff_id | Nonempty immutable dataset/review version |
| contract_version | String 2.0 |
| task | podium or lap_time |
| stage_or_mode | post_qualifying, post_grid or historical, consistent with task |
| files | List of objects: role, relative_path, sha256, row_count, ordered_columns |
| races | List of objects: race_id, race_start_utc, source_session_keys, eligible_driver_ids, prediction_cutoffs_utc |
| lineage_path | Relative path to field-lineage table |
| crosswalk_paths | List of relative paths to reviewed identity mappings |
| quality_report_path | Relative path to exclusions, coverage, conflicts and assumption decisions |
| assumption_decisions | Object recording A1 age convention, A2 weather rule/staleness, A3 validity/regime scope where applicable |
| review_status | verified, corrected or unresolved |
| reviewer | Nonempty accountable M2 reviewer |
| reviewed_at_utc | UTC decision timestamp |
| approved_for_modeling | Boolean, explicitly set by M2; never inferred from smoke tests |

Role values in files are features, labels, metadata, crosswalk or lineage.
Only features go to inference; labels are separately loaded for training or
retrospective evaluation. Each race entry identifies actual source sessions and
cutoffs; each historical lap's exact cutoff remains in its input row.
Scenario requests do not pretend to have an M2-approved historical target
handoff; use reviewed identity/model support plus separate user-scenario lineage.

A true approved_for_modeling requires resolved relevant source conflicts,
documented availability/validity decisions, matching file hashes, and corrections
actually applied to a newly versioned dataset where necessary. A checklist row
marked corrected is not proof that a feature file was changed. Pending/unsupported
rows require explicit quarantine and coverage reporting, not automatic approval.
An unresolved final grid blocks podium post_grid; it does not automatically
block a separately approved post_qualifying table.

### 7.2 M3 artifact requirements

Use task/stage-specific v2 artifact locations, separate from any v1 artifacts.
Persist Pipeline/ColumnTransformer objects with joblib and metadata recording:

contract_version, task, model_name, model_version, stage_or_scope, ordered feature
schema, training handoff IDs and source hashes, race/date partitions and cutoff,
preprocessing/category definitions, supported circuit/driver/compound domains,
numeric training ranges, assumption decisions, evaluation results, random seeds,
and Python/library versions. Pin dependencies and test persisted/API prediction
parity. Fit no model in a prediction call.

Reject missing artifacts, wrong task/model/contract/schema, unsupported scope,
invalid/mixed podium races, duplicate keys, leaked labels/results and missing
required verification context. A v1 artifact is not a v2 artifact simply because
its filename matches. Missing models produce explicit unavailable errors, never
mock scores represented as trained results.

### 7.3 M1 behavior

M1 keeps separate podium and lap-time presentations. It displays podium scores
as independent top-three probabilities and selections, and lap predictions in
seconds. It prominently labels scenario outputs as hypothetical clean practice
laps under supplied assumptions, not GP race-lap forecasts. Show numeric
extrapolation flags and unsupported-input errors.

M1 uses the approved handoff ID/hash context for empirical inputs, preserves UTC
cutoffs and explicit grid attestation, and does not certify M2 decisions itself.
No lap-regression output is added to podium features in v2. Any future coupling
requires a separate contract revision and chronological out-of-fold predictions
for training, never in-sample stacking.

## 8. Required acceptance checks before implementation is declared complete

- Podium stage schemas, ranking and tie behavior remain compatible; v2 outputs
  name only random_forest, and artifacts are isolated from legacy code/models.
- Lap schemas, categorical support, age boundaries/reused tires, invalid/overlap
  stint joins, missing targets and clean-lap decisions have regression tests.
- Backward-only weather matching, freshness, missing timestamps, scenario labels
  and final-stint/target leakage prevention have tests.
- Changing race outcomes or future observations cannot change earlier features.
- Chronological weekend grouping, train-only transformations, artifact reload
  parity, missing-artifact errors and task separation have tests.
- M1 scenario labeling, independent outputs and error behavior are verified.
- Original five-race dataset, v1 contract and verification package remain
  unchanged unless a later explicit M2 correction produces a new version.

Open M2 confirmations: source/identity crosswalks and conflict adjudication;
eligible rosters and final grids; actual forecast/publication availability;
A1 tire-age numbering and reused-tire handling; A2 weather staleness and timing;
A3 clean-lap/flag/deletion and wet/dry scope; circuit/layout and driver support;
and the formal reviewed, versioned handoff. None is silently certified here.
