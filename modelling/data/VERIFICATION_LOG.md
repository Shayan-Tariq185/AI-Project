# M2 Verification Log

## Scope

The implementation verified the cached five-race 2024 pilot offline.

| Race | Race/driver coverage | Podium label count | Grid structure | M2 approval |
|---|---:|---:|---|---|
| 2024_bahrain_gp | 20 | 3 | True | unresolved |
| 2024_saudi_arabia_gp | 20 | 3 | True | unresolved |
| 2024_australia_gp | 19 | 3 | True | unresolved |
| 2024_japan_gp | 20 | 3 | True | unresolved |
| 2024_china_gp | 20 | 3 | True | unresolved |

## Verification items

- Raw cache coverage: passed for the current five-race cached pilot.
- Driver uniqueness: passed in the combined podium feature tables.
- Exactly three podium positives: check per race before approval.
- Negative or zero qualifying gaps: reject negative values.
- Negative or zero lap durations: keep invalid rows excluded.
- Duplicate race/driver keys: reject.
- Weather timestamps: must fall inside the qualifying/practice session in a reviewed export.
- Leakage: race outcomes and race telemetry are kept out of forecast feature tables.
- Final grid: unresolved.
- Forecast cutoffs: unresolved.
- Lap/table approval: blocked by missing cached stints.
- Jolpica verification: not implemented.

## Evidence locations

- `modelling/data/pilot_2024/`
- `modelling/data/2024_<country>/raw/`
- `modelling/verification/issues.csv`
- `modelling/verification/CHECKLIST.md`
