# Delivery and verification evidence

Deliver an immutable version directory containing the files below. Relative paths
must stay within it. `handoff.template.json` is deliberately unresolved with
approved_for_modeling=false; populate real evidence and hashes before M2 review.
It is not currently a loadable/approved data package.

| File | Content / loader requirement |
|---|---|
| features.csv | Exact 13-column historical schema; only reviewed included rows |
| labels.csv | Exact two-column target schema; one target per included example |
| examples.csv | Per-example clean-lap, stint and target-timing evidence (columns below) |
| weather.csv | Hashed practice observations with session_key, date, available_at_utc, track_temperature |
| drivers.csv | Reviewed crosswalk with race_id, driver_id, driver_number, driver_name, review_status |
| circuits.csv | Reviewed crosswalk with race_id, circuit_id, review_status |
| lineage.csv | Exact field-lineage columns below; 13 records per included example |
| quality.json | One JSON object containing unresolved_issues plus coverage, exclusions, conflicts and policy notes |
| exclusions.csv | Candidate-level excluded/quarantined decisions and evidence references |
| unresolved_records.csv | Open issues, impact, owner and disposition; template header provided |
| raw/ | Immutable cached source responses, request/retrieval metadata and revision evidence |
| handoff.json | Completed versioned manifest with accountable M2 sign-off |

The current loader requires the literal sidecar names `examples.csv` and
`weather.csv`. It locates features and labels by their unique roles, crosswalks
through crosswalk_paths, and lineage/quality via their manifest paths. Use the
names above to avoid ambiguity. List all review tables in files with allowed
roles; raw JSON arrays can instead be referenced by lineage with their hashes.
Keep raw evidence within the package, never absolute or parent-traversing paths.

`examples.csv` must have unique example_id and these required columns (extras
are metadata only):

```text
example_id,session_name,clean_flying_lap_verified,stint_lap_start,stint_lap_end,tyre_age_at_start,lap_start_utc,lap_end_utc,target_available_at_utc,stint_available_at_utc,compound
```

Use actual booleans for clean_flying_lap_verified after CSV loading. Provide
Practice 1/2/3 session names, numeric stint bounds/starting age and UTC times.
Membership must cover the target lap; derived age and compound must match features.
Keep raw stint IDs, interval-uniqueness proof, pit/flag/deletion decisions and
reviewer references as additional metadata. The loader checks the selected
interval but does not reconstruct all competing raw intervals or independently
establish official validity: M2 must supply and review that evidence.
Target availability must follow completion; stint availability must be no later
than lap start. All targets used to fit an earlier partition must be available
before the next partition's prediction cutoffs.

Full contract crosswalks also include race season/round, meeting/session keys,
OpenF1 driver/circuit IDs, layout version and optional Jolpica IDs (contract §3.2).
Supply these as additional versioned crosswalk evidence, preserving the loader's
minimal drivers.csv/circuits.csv views. Jolpica identifiers may be null; this
package introduces no Jolpica integration. Explain practice substitutions and
layout changes rather than relying on name matching.

`lineage.csv` has exactly:

```text
task,row_key,field_name,selected_source,source_record_refs,derived_from,observed_at_utc,available_at_utc,retrieved_at_utc,review_status,reviewer,reviewed_at_utc,resolution_notes
```

For each included example and each of its 13 input columns:

- task is lap_time; row_key is JSON such as `{"example_id":"YOUR_EXAMPLE_ID"}`.
- field_name is an exact input column name. There is exactly one record per pair.
- selected_source is openf1 or derived for these field mappings; historical loader
  also accepts jolpica, but do not substitute it for detailed lap/tire/weather data.
- source_record_refs is a nonempty JSON list of objects, each with source,
  relative_path, record_key and sha256. Use an unambiguous record_key containing
  the actual session/driver/lap/stint or weather keys. Reference real cached
  records, not a circular reference to the exported feature value as its proof.
- derived_from is a JSON list naming upstream field/record references; explain
  tire age arithmetic and canonical-ID mapping. Preserve formula/policy version.
- observed_at_utc describes the event; available_at_utc describes when its value
  was available. Both must be <= cutoff when present; availability is mandatory
  for ready inputs. retrieved_at_utc records later acquisition, never substitutes
  for historical availability. Document unavailable timestamps as unresolved.
- review_status is verified/corrected only for ready rows. Name reviewer, review
  UTC and resolution. Review itself may happen later than the historical cutoff.

Use normal CSV quoting for JSON-valued cells. Record target and validity provenance
in examples/exclusion evidence rather than adding label fields to input lineage.

Each files entry in handoff.json must contain role, relative_path, sha256 (actual
file bytes), row_count and ordered_columns. Roles are features, labels, metadata,
crosswalk or lineage. For CSV, row_count excludes the header. For quality.json,
use a single object (row_count 1; ordered_columns are its top-level key order).
Compute after final serialization, then freeze files. Recompute on correction and
issue a new handoff_id. Preserve raw hashes too. A matching hash proves integrity,
not truth, clean-lap status or historical availability.

The manifest races array has one record per canonical weekend: race_id,
race_start_utc, source_session_keys (practice is a list of integer keys),
eligible_driver_ids matching reviewed drivers, and prediction_cutoffs_utc
documenting the historical window. Exact per-example cutoff remains in features.
Record the GP race session/meeting and practice session selection evidence too.

For example, populate structures like these with reviewed values (the strings
below are placeholders, not source records):

```json
{
  "file_entry_shape": {
    "role": "features",
    "relative_path": "features.csv",
    "sha256": "REPLACE_WITH_64_HEX_DIGITS",
    "row_count": 0,
    "ordered_columns": ["REPLACE_WITH_ALL_13_COLUMNS_IN_ORDER"]
  },
  "race_entry_shape": {
    "race_id": "REPLACE_WITH_CANONICAL_WEEKEND_ID",
    "race_start_utc": "REPLACE_WITH_VERIFIED_UTC_TIMESTAMP",
    "source_session_keys": {"practice": [], "race": null},
    "eligible_driver_ids": [],
    "prediction_cutoffs_utc": {
      "historical_start": "REPLACE_WITH_FIRST_CUTOFF",
      "historical_end": "REPLACE_WITH_LAST_CUTOFF"
    }
  }
}
```

These shape labels are explanatory, not manifest keys. Insert the completed
objects into files and races respectively; do not copy the placeholders as data.

M2 must explicitly decide:

- A1: verified/corrected; convention completed_laps_before_target, with numbering,
  pit-out and reused-tire evidence.
- A2: verified/corrected; matching latest_available_at_or_before_cutoff and an
  approved finite positive max_age_seconds, supported by a freshness rationale.
- A3: verified/corrected; scope clean_normal_practice_flying_laps and an explicit
  supported_compounds list, plus validity and wet/dry regime decisions.

For unresolved work, fill unresolved_records.csv with a candidate key, affected
field, missing/conflicting values, source references, issue, owner, proposed action
and resolution. Distinguish excluded (policy decision), quarantined (pending),
corrected (applied and evidenced) and included (approved). Keep original values.
Report total candidate = included + excluded + quarantined with no overlap, plus
counts by weekend/session/reason and category coverage. Reviewed exclusions can
coexist with an approved subset, but all issues affecting included rows must be
resolved. The loader rejects any nonempty quality.json unresolved_issues list;
use an unapproved draft for open issues, or a separately approved subset with
explicit quarantine coverage and no unresolved claims about its included rows.
Never erase the external issue log to obtain a loader pass.

Only the accountable M2 reviewer may set approved_for_modeling=true, after
CHECKLIST.md and all supporting decisions are complete. A schema check, template,
synthetic example or loader pass cannot provide that certification. Ready data
still requires M3 review of evaluation sufficiency and categorical support.
