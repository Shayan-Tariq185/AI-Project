# Podium v2 implementation and M1 compatibility

This implements the podium portion of CONTRACT_v2.md only. The independent
Linear Regression task remains unimplemented. Neither this code nor the
synthetic tests approves the real five-race pilot.

## Unchanged M1 API

    predict_podium(race_data: pd.DataFrame, stage: str) -> pd.DataFrame

The eight output columns and deterministic ranking are unchanged. Both stages
are supported. model_name is always random_forest. The model sees only its
stage's explicit feature list; grid is never a post-qualifying modeling feature.

V2 intentionally tightens evidence and artifact compatibility. M1 must attach a
path to the M2-approved handoff without adding columns to its feature table:

    race_data.attrs['m2_handoff_path'] = 'path/to/stage/handoff.json'
    # Additionally required for post_grid:
    race_data.attrs['grid_verified'] = True
    result = predict_podium(race_data, 'post_grid')

Alternatively, attrs['m2_handoffs'] can map each stage to its own handoff path.
The same mapping is used by training. A boolean grid flag or a completed
spreadsheet alone does not replace approved/hash-matched evidence. M1 must not
invent that approval. Missing artifacts are reported before handoff loading;
there is no mock prediction fallback.

## M2 handoff package conventions

The contract defines the handoff fields. The following local storage conventions
make that contract executable; no existing M2 file is rewritten.

- All evidence references are relative to the handoff JSON's directory and must
  stay inside that package. Each referenced file must exist and match SHA-256.
- files has exactly one features CSV per handoff/stage, with the contract's
  ordered identity/feature columns. Labels, when present, are a separate CSV
  containing race_id, driver_number, is_podium_actual; training requires them.
- Every files entry declares role, relative_path, sha256, row_count and
  ordered_columns. CSV or JSON metadata is supported; a JSON object is one row.
- lineage_path points to a hashed lineage table; crosswalk_paths identify hashed
  crosswalk tables. The driver crosswalk includes race_id, driver_number,
  driver_id and review_status. Eligibility must agree with the feature rows.
- quality_report_path points to hashed metadata. It must include an
  unresolved_issues JSON array, empty for the approved task/stage. Issues for
  unrelated future work are not grounds to auto-approve or auto-reject this task;
  M2 must scope its handoff and explicitly resolve its relevant evidence.
- Each races entry identifies race_id, race_start_utc, source_session_keys
  (including positive integer qualifying and race keys), eligible_driver_ids,
  and prediction_cutoffs_utc keyed by the approved stage.
- Lineage covers every approved feature-table field/row, using JSON row_key
  objects with race_id and driver_number. Every field has verified/corrected
  status, reviewer, UTC review time, and availability no later than the cutoff.
  Optional observation time cannot follow the cutoff.
- source_record_refs is a JSON array of source, relative_path, record_key and
  sha256 objects. derived_from is a JSON array of upstream references. Sources
  may be openf1, jolpica or derived; no source fetch or Jolpica adapter exists here.
- approved_for_modeling must be explicitly true, review_status must be verified
  or corrected, and reviewer/reviewed_at_utc must be supplied. Metadata, labels,
  crosswalks, input values and complete eligible-driver sets are checked.
- UTC race dates in training must match handoff race starts. Local/naive dates
  cannot silently receive a timezone. M2 must review and version actual corrected
  tables; a status string is not evidence that a correction was applied.

The JSON and evidence remain trusted local handoff documents, not cryptographic
authentication of a reviewer. Hashes identify contents and detect changes; they
do not independently certify the truth of a source or M2's decisions.

## Training and evaluation

Training retains the ten-reviewed-race minimum and complete-race 60/20/20
chronological partitions. It fits only the fixed shallow Random Forest:
200 trees, maximum depth 4, minimum leaf size 3, seed 42, one worker.

Median imputers fit inside each stage pipeline on training rows only. There is
no scaling or Logistic Regression candidate/model-selection loop. An entirely
unobserved training feature stops training for an explicit modeling decision.

The initial forest is evaluated on validation. The fixed architecture is then
refit on train plus validation and evaluated once on later test races. Training
source/label hashes, reviewed handoff IDs, training cutoff, feature ranges,
partitions, preprocessing and library versions are recorded. Saved predictions
are checked through the public API for parity with evaluation.

The training workflow may join separately approved labels and race dates for
fitting. The model itself is fitted with only the stage feature columns. The
legacy training CLI now requires both stage handoffs:

    .venv\Scripts\python.exe m3.py reviewed_training_workflow.csv --grid-verified --post-qualifying-handoff path/to/qualifying/handoff.json --post-grid-handoff path/to/grid/handoff.json

This is a usage example, not authorization to train the unreviewed pilot.
All review checks for both stages run before fitting or writing artifacts.

Evaluation retains correct top-three selections, exact-set rates, stage-appropriate
qualifying/grid baselines, a real first miss if present, and selection
precision/recall. It additionally reports average precision, Brier score, and
precision/recall at the fixed 0.5 threshold. Baselines with fewer than three known
positions are explicitly unavailable, not completed with invented selections.

## Artifacts and legacy compatibility

New artifacts live under artifacts/v2/podium/:
post_qualifying.joblib/.json, post_grid.joblib/.json and evaluation.json.

Metadata requires contract_version 2.0, task podium, model_name random_forest,
the matching stage/features and persisted model version. The loader checks
metadata and pipeline hash before deserialization, and requires compatible
pinned libraries/Python minor version and a fitted RandomForestClassifier
pipeline with the expected feature schema. Only load trusted local joblib files.

V1 artifacts are never searched as a usable fallback. A detected old artifact,
including a v1 Random Forest, produces an explicit compatibility error. Do not
relabel its JSON to v2. A separately authorized run on M2-approved history must
produce the v2 artifact. Existing artifacts are neither deleted nor regenerated
by migration tests.

evaluation.json now has one validation/test result per stage plus model identity;
winner, candidate-model maps and tie_policy are removed. Readers of that report
must migrate. The M1 prediction signature and output columns do not change.

## Tests and preserved evidence

Run the complete suite from modelling/:

    .venv\Scripts\python.exe -B -m pytest -q

pytest.ini includes existing podium, pilot and verification tests plus the new
migration tests. conftest.py creates clearly labeled SYNTHETIC-ONLY handoffs;
all generated synthetic evidence/models stay under .test-work/. These are code
tests, not M2 approval or accuracy evidence for any real Grand Prix.

The original contracts, existing race CSVs/caches, collectors, smoke script and M2
verification package are unchanged. Do not run collection or the writing smoke
script merely to migrate models. Linear Regression and Jolpica integration remain
separate future tasks.
