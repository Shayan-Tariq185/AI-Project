# M2 handoff: clean practice lap-time data

Prepare a versioned, reviewed OpenF1 historical dataset for the existing Linear
Regression model. One row represents one clean normal practice flying lap,
with inputs reconstructed at lap start and its duration supplied separately as
a later target. Qualifying, sprint, shootout and race laps are outside scope.
This package is guidance and templates, not data approval or collection authority.

Read [SCHEMA.md](SCHEMA.md), then [SOURCES_AND_JOINS.md](SOURCES_AND_JOINS.md),
[EVIDENCE.md](EVIDENCE.md) and complete [CHECKLIST.md](CHECKLIST.md).
`synthetic_features.csv` and `synthetic_labels.csv` contain invented examples only.
Every example/person/weekend/layout identifier is prefixed SYNTHETIC. Session
numbers, times and durations are fictional too. The two files demonstrate the
training interface; they are deliberately not an approved handoff or a sufficient
training dataset. Do not combine the labels into the feature export or add a
synthetic marker column: exact schemas forbid extra columns.

The authority is [CONTRACT_v2.md](../CONTRACT_v2.md), especially sections 2, 3,
5, 6 and 7. Implementation details were checked against [lap_model.py](../lap_model.py),
[lap_handoff.py](../lap_handoff.py), [LAP_TIME_V2.md](../LAP_TIME_V2.md) and
[test_lap_model.py](../test_lap_model.py). Source mappings below come from these
local project specifications; no live API documentation or data was fetched.

The contract's proposed two-argument prediction API differs from the implemented
`predict_lap_time(lap_data)`: callers set `lap_data.attrs['mode']='historical'`
and `lap_data.attrs['m2_handoff_path']` to the reviewed manifest path. CSV does not
retain attrs. M2 supplies files and review decisions; M3 handles fitting and
preprocessing later. This package neither invokes training nor changes contracts.

Run the read-only example/schema checks from `modelling/`:

```powershell
.venv\Scripts\python.exe -B m2_lap_handoff/validate_examples.py
```

Passing checks confirms example schema and protected-file integrity only. It
does not verify real source availability, clean laps, category support or M2 approval.
